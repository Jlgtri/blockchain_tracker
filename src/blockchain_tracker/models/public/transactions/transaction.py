from datetime import datetime
from re import Pattern, compile, match
from typing import TYPE_CHECKING, ClassVar, List, Self, Type

from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.sql.schema import CheckConstraint, Column, ForeignKey
from sqlalchemy.sql.sqltypes import DateTime, String

from ..._mixins import Timestamped
from ...base import Base
from ..tokens.token import Token
from ..wallets.wallet import Wallet

if TYPE_CHECKING:
    from ...tg.chats.chat_message import ChatMessage
    from .transaction_amount import TransactionAmount


class Transaction(Timestamped, Base):
    BTC_REGEXP: ClassVar[Pattern] = compile(
        r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$'
    )
    TRON_REGEXP: ClassVar[Pattern] = compile(r'T[A-Za-z1-9]{33}')

    hash: Mapped[str] = Column(
        String(255),
        CheckConstraint("hash <> ''"),
        primary_key=True,
    )
    wallet_address: Mapped[str] = Column(
        Wallet.address.type,
        ForeignKey(Wallet.address, onupdate='RESTRICT', ondelete='RESTRICT'),
        nullable=False,
    )
    from_address: Mapped[str] = Column(
        Wallet.address.type,
        nullable=False,
    )
    token_address: Mapped[str] = Column(
        Token.address.type,
        ForeignKey(Token.address, onupdate='RESTRICT', ondelete='RESTRICT'),
        nullable=False,
    )
    timestamp: Mapped[datetime] = Column(DateTime, nullable=False)

    wallet: Mapped['Wallet'] = relationship(
        back_populates='transactions',
        lazy='joined',
        cascade='save-update',
    )
    token: Mapped['Token'] = relationship(
        back_populates='transactions',
        lazy='joined',
        cascade='save-update',
    )
    amounts: Mapped[List['TransactionAmount']] = relationship(
        back_populates='transaction',
        lazy='selectin',
        cascade='save-update',
    )
    telegram_chat_messages: Mapped[List['ChatMessage']] = relationship(
        back_populates='transaction',
        lazy='noload',
        cascade='save-update',
    )

    @property
    def url(self: Self, /) -> str:
        if match(self.BTC_REGEXP, self.wallet_address):
            return (
                'https://www.blockchain.com/explorer/transactions/btc/'
                + self.hash
            )
        elif match(self.TRON_REGEXP, self.wallet_address):
            return 'https://tronscan.org/#/transaction/' + self.hash
        else:
            raise ValueError(
                'Wallet address `%s` does not match known explorers!'
                % self.wallet_address
            )

    @classmethod
    def token_address_url(cls: Type[Self], address: str, /) -> str:
        if match(cls.TRON_REGEXP, address):
            return 'https://tronscan.org/#/contract/' + address
        else:
            raise ValueError(
                'Token address `%s` does not match known explorers!' % address
            )

    @classmethod
    def address_url(cls: Type[Self], address: str, /) -> str:
        if match(cls.BTC_REGEXP, address):
            return (
                'https://www.blockchain.com/explorer/addresses/btc/' + address
            )
        elif match(cls.TRON_REGEXP, address):
            return 'https://tronscan.org/#/address/' + address
        else:
            raise ValueError(
                'Wallet address `%s` does not match known explorers!' % address
            )

    @classmethod
    def shorten(cls: Type[Self], address: str, /) -> str:
        if match(cls.BTC_REGEXP, address):
            return address[:4] + '-' + address[-4:]
        elif match(cls.TRON_REGEXP, address):
            return address[:4] + '..' + address[-4:]
        else:
            return address
