from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from logging import Logger, getLogger
from re import match
from typing import ClassVar, Final, Optional, Self

from aiogram import Bot
from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from anyio import Event
from anyio import create_memory_object_stream as stream
from anyio import create_task_group
from anyio import sleep as asleep
from anyio.streams.memory import MemoryObjectReceiveStream as Receiver
from anyio.streams.memory import MemoryObjectSendStream as Sender
from dateutil.tz.tz import tzlocal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.ext.asyncio.scoping import async_scoped_session
from sqlalchemy.sql.expression import select
from sqlalchemy.sql.functions import max, now

from .export import export_transaction
from .fetch import (
    fetch_bitcoin_wallet_transactions,
    fetch_tradersroom_token,
    fetch_tradersroom_wallets,
    fetch_tron_wallet_transactions,
)
from .models.public.transactions.transaction import Transaction
from .models.public.wallets.wallet import Wallet, WalletHost
from .models.tg.chats.chat_message import ChatMessage
from .utils.get_bind import Bind, get_bind
from .utils.wrap_exc import wrap_exc


@dataclass(init=False, frozen=True)
class BlockChainTracker(object):
    email: Final[str]
    password: Final[str]
    chat_id: Final[int]

    _bot: Final[Bot]
    _engine: Final[AsyncEngine]
    _Session: Final[async_scoped_session]
    _session: Final[ClientSession]
    _logger: Final[Logger]

    EXPORT_LIMITER: ClassVar[AsyncLimiter] = AsyncLimiter(1, 1)
    TRANSACTIONS_PERIOD: ClassVar[timedelta] = timedelta(minutes=1)
    TRANSACTIONS_LIMITER: ClassVar[AsyncLimiter] = AsyncLimiter(
        1, TRANSACTIONS_PERIOD.total_seconds()
    )
    WALLETS_PERIOD: ClassVar[timedelta] = timedelta(minutes=10)
    WALLETS_LIMITER: ClassVar[AsyncLimiter] = AsyncLimiter(
        1, WALLETS_PERIOD.total_seconds()
    )

    def __init__(
        self: Self,
        /,
        email: str,
        password: str,
        chat_id: int,
        bind: Bind,
        bot: Bot,
        session: Optional[ClientSession] = None,
        *,
        logger_name: Optional[str] = None,
    ) -> None:
        if not email or not password or not chat_id:
            raise Exception()
        elif not isinstance(bot, Bot):
            raise Exception()
        engine, Session = get_bind(bind)
        object.__setattr__(self, 'email', email)
        object.__setattr__(self, 'password', password)
        object.__setattr__(self, 'chat_id', chat_id)
        object.__setattr__(self, 'wallets', {})
        object.__setattr__(self, '_engine', engine)
        object.__setattr__(self, '_Session', Session)
        object.__setattr__(self, '_bot', bot)
        object.__setattr__(
            self,
            '_session',
            session if isinstance(session, ClientSession) else ClientSession(),
        )
        object.__setattr__(
            self,
            '_logger',
            getLogger(logger_name or self.__class__.__name__),
        )

    async def run(self: Self, /) -> None:
        self._logger.info('Started!')
        event = Event()
        sender, receiver = stream[str](float('inf'))
        async with self._session, create_task_group() as tg, sender, receiver:
            tg.start_soon(wrap_exc(self.fetch_wallets, self._Session), event)
            tg.start_soon(
                wrap_exc(self.fetch_wallet_transactions),
                event,
                sender.clone(),
            )
            tg.start_soon(
                wrap_exc(self.export_wallet_transactions),
                receiver.clone(),
            )
        self._logger.info('Finished!')

    async def fetch_wallets(
        self: Self,
        event: Event,
        /,
        index: Optional[int] = None,
    ) -> None:
        while not index:
            oldest_time_since = None
            for host in WalletHost._value2member_map_.values():
                time_since = await self._Session.scalar(
                    select(now() - max(Wallet.updated_at)).filter_by(
                        host=host.value
                    )
                )
                if time_since is not None and time_since < self.WALLETS_PERIOD:
                    if oldest_time_since is None or (
                        oldest_time_since < time_since
                    ):
                        oldest_time_since = time_since
                    continue
                user_id_token = await fetch_tradersroom_token(
                    self._session,
                    host,
                    self.email,
                    self.password,
                    index=index,
                )
                if not user_id_token:
                    continue

                wallets = await fetch_tradersroom_wallets(
                    self._session,
                    host,
                    *user_id_token,
                    index=index,
                )
                for name, address in wallets.items():
                    await self._Session.merge(
                        Wallet(
                            host=host.value,
                            name=name,
                            address=address,
                            updated_at=datetime.now(tzlocal()),
                        )
                    )
                await self._Session.commit()
            await self._Session.remove()
            event.set()
            time_to_sleep = self.WALLETS_PERIOD
            if oldest_time_since is not None:
                time_to_sleep -= oldest_time_since
            await asleep(time_to_sleep.total_seconds())

    async def fetch_wallet_transactions(
        self: Self,
        event: Event,
        sender: Sender[str],
        /,
        index: Optional[int] = None,
    ) -> None:
        async with sender:
            await event.wait()
            while not index:
                async with self.TRANSACTIONS_LIMITER:
                    for wallet in await self._Session.scalars(select(Wallet)):
                        if match(Transaction.BTC_REGEXP, wallet.address):
                            transactions = (
                                await fetch_bitcoin_wallet_transactions(
                                    self._session,
                                    wallet.address,
                                    index=index,
                                )
                            )
                        elif match(Transaction.TRON_REGEXP, wallet.address):
                            transactions = (
                                await fetch_tron_wallet_transactions(
                                    self._session,
                                    wallet.address,
                                    index=index,
                                )
                            )
                        else:
                            self._logger.warning(
                                '%sUnknown wallet address `%s`!',
                                '[%s] ' % index if index is not None else '',
                                wallet.address,
                            )
                            continue

                        transaction_hashes = []
                        last_transaction_at = await self._Session.scalar(
                            select(max(Transaction.timestamp)).filter_by(
                                wallet_address=wallet.address
                            )
                        )
                        for transaction in transactions:
                            with suppress(IntegrityError):
                                async with self._Session.begin_nested():
                                    transaction.token = (
                                        await self._Session.merge(
                                            transaction.token
                                        )
                                    )
                                    self._Session.add(transaction)
                                    for amount in transaction.amounts:
                                        self._Session.add(amount)
                                if last_transaction_at is not None:
                                    transaction_hashes.append(transaction.hash)
                        await self._Session.commit()
                        for transaction_hash in transaction_hashes:
                            await sender.send(transaction_hash)
                    await self._Session.remove()

    async def export_wallet_transactions(
        self: Self,
        receiver: Receiver[str],
        /,
        index: Optional[int] = None,
    ) -> None:
        async with receiver:
            async for transaction_hash in receiver:
                if await self._Session.scalar(
                    select(ChatMessage).filter_by(
                        transaction_hash=transaction_hash
                    )
                ):
                    await self._Session.remove()
                    self._logger.info(
                        '%sSkipped exporting transaction `%s`!',
                        '[%s] ' % index if index is not None else '',
                        transaction_hash,
                    )
                    continue
                transaction = await self._Session.get(
                    Transaction, transaction_hash
                )
                if transaction is None:
                    self._logger.info(
                        '%sInvalid transaction `%s`!',
                        '[%s] ' % index if index is not None else '',
                        transaction_hash,
                    )
                    continue
                async with self.EXPORT_LIMITER:
                    message = await export_transaction(
                        self._bot,
                        transaction,
                        self.chat_id,
                        index=index,
                    )
                with suppress(IntegrityError):
                    self._Session.add(
                        ChatMessage(
                            transaction_hash=transaction_hash,
                            chat_id=self.chat_id,
                            message_id=message.message_id,
                        )
                    )
                    await self._Session.commit()
                await self._Session.remove()
