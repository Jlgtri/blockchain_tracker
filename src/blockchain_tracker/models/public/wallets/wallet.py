from enum import StrEnum, auto
from typing import TYPE_CHECKING, Final, Self

from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.sql.schema import CheckConstraint, Column
from sqlalchemy.sql.sqltypes import Enum, String

from ..._mixins import Timestamped
from ...base import Base

if TYPE_CHECKING:
    from ..transactions.transaction import Transaction


class WalletHostAction(StrEnum):
    login: Final[str] = auto()
    fetch_wallets: Final[str] = auto()


class WalletHost(StrEnum):
    benefort: Final[str] = 'benefort.org'
    fianit: Final[str] = 'fianit.net'
    whitetrade: Final[str] = 'whitetrade.net'

    def key(self: Self, action: WalletHostAction, /) -> str:
        if self == self.benefort:
            if action == WalletHostAction.login:
                return ''
            elif action == WalletHostAction.fetch_wallets:
                return ''
        elif self == self.fianit:
            if action == WalletHostAction.login:
                return '9913cab1ae0ebab298863cda7086f7c9'
            elif action == WalletHostAction.fetch_wallets:
                return '12977a71be9e738190369850b437e3c9'
        elif self == self.whitetrade:
            if action == WalletHostAction.login:
                return '434b4a60f39960b0822fc68c51b39b3b'
            elif action == WalletHostAction.fetch_wallets:
                return '9e611606476d548ab07ebeb500f0cacf'
        else:
            raise RuntimeError('`%s` is not a known host!' % self)
        raise RuntimeError('`%s` is not a known action!' % action)

    def rand_param(self: Self, action: WalletHostAction, /) -> str:
        if self == self.benefort:
            if action == WalletHostAction.login:
                return ''
            elif action == WalletHostAction.fetch_wallets:
                return ''
        elif self == self.fianit:
            if action == WalletHostAction.login:
                return '77097949'
            elif action == WalletHostAction.fetch_wallets:
                return '88539607'
        elif self == self.whitetrade:
            if action == WalletHostAction.login:
                return '27320033'
            elif action == WalletHostAction.fetch_wallets:
                return '71134563'
        else:
            raise RuntimeError('`%s` is not a known host!' % self)
        raise RuntimeError('`%s` is not a known action!' % action)


class Wallet(Timestamped, Base):
    address: Mapped[str] = Column(
        String(255),
        CheckConstraint("address <> ''"),
        primary_key=True,
    )
    host: Mapped[WalletHost] = Column(Enum(WalletHost), nullable=False)
    name: Mapped[str] = Column(
        String(255),
        CheckConstraint("name <> ''"),
        nullable=False,
    )

    transactions: Mapped['Transaction'] = relationship(
        back_populates='wallet',
        lazy='noload',
        cascade='save-update',
    )
