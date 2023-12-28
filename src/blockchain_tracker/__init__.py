from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    TransactionData,
    fetch_bitcoin_wallet_transactions,
    fetch_tradersroom_token,
    fetch_tradersroom_wallets,
    fetch_tron_wallet_transactions,
)
from .models.public.transactions.transaction import Transaction
from .models.public.wallets.wallet import Wallet
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
        sender, receiver = stream[TransactionData](float('inf'))
        async with self._session, create_task_group() as tg, sender, receiver:
            tg.start_soon(wrap_exc(self.fetch_wallets), event)
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
            time_since = await self._Session.scalar(
                select(now() - max(Wallet.updated_at))
            )
            if time_since is not None and time_since < self.WALLETS_PERIOD:
                event.set()
                await self._Session.remove()
                await asleep(
                    (self.WALLETS_PERIOD - time_since).total_seconds()
                )
            token = await fetch_tradersroom_token(
                self._session,
                self.email,
                self.password,
                index=index,
            )
            wallets = await fetch_tradersroom_wallets(
                self._session,
                token,
                index=index,
            )
            for name, address in wallets.items():
                await self._Session.merge(
                    Wallet(
                        name=name,
                        address=address,
                        updated_at=datetime.now(tzlocal()),
                    )
                )
            await self._Session.commit()
            await self._Session.remove()
            event.set()

    async def fetch_wallet_transactions(
        self: Self,
        event: Event,
        sender: Sender[TransactionData],
        /,
        index: Optional[int] = None,
    ) -> None:
        async with sender:
            await event.wait()
            while not index:
                async with self.TRANSACTIONS_LIMITER:
                    for wallet in await self._Session.scalars(select(Wallet)):
                        if match(TransactionData.BTC_REGEXP, wallet.address):
                            transactions = (
                                await fetch_bitcoin_wallet_transactions(
                                    self._session,
                                    wallet.address,
                                    index=index,
                                )
                            )
                        elif match(
                            TransactionData.TRON_REGEXP, wallet.address
                        ):
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

                        last_transaction_at = await self._Session.scalar(
                            select(max(Transaction.timestamp)).filter_by(
                                wallet_address=wallet.address
                            )
                        )
                        for transaction in transactions:
                            with suppress(IntegrityError):
                                async with self._Session.begin_nested():
                                    self._Session.add(
                                        Transaction(
                                            hash=transaction.hash,
                                            wallet_address=wallet.address,
                                            timestamp=datetime.fromtimestamp(
                                                transaction.timestamp,
                                                timezone.utc,
                                            ),
                                        )
                                    )
                                if last_transaction_at is not None:
                                    await sender.send(transaction)
                        await self._Session.commit()
                    await self._Session.remove()

    async def export_wallet_transactions(
        self: Self,
        receiver: Receiver[TransactionData],
        /,
        index: Optional[int] = None,
    ) -> None:
        async with receiver:
            async for transaction in receiver:
                if await self._Session.scalar(
                    select(ChatMessage).filter_by(
                        transaction_hash=transaction.hash
                    )
                ):
                    await self._Session.remove()
                    self._logger.info(
                        '%sSkipped exporting transaction `%s`!',
                        '[%s] ' % index if index is not None else '',
                        transaction.hash,
                    )
                    continue
                async with self.EXPORT_LIMITER:
                    message = await export_transaction(
                        self._bot, transaction, self.chat_id, index=index
                    )
                with suppress(IntegrityError):
                    self._Session.add(
                        ChatMessage(
                            transaction_hash=transaction.hash,
                            chat_id=self.chat_id,
                            message_id=message.message_id,
                        )
                    )
                    await self._Session.commit()
                await self._Session.remove()
