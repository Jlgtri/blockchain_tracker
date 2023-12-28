from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.sql.schema import CheckConstraint, Column, ForeignKey
from sqlalchemy.sql.sqltypes import DateTime, String

from ..._mixins import Timestamped
from ...base import Base
from ..wallets.wallet import Wallet

if TYPE_CHECKING:
    from ...tg.chats.chat_message import ChatMessage


class Transaction(Timestamped, Base):
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
    timestamp: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    wallet: Mapped['Wallet'] = relationship(
        back_populates='transactions',
        lazy='joined',
        cascade='save-update',
    )
    telegram_chat_messages: Mapped[List['ChatMessage']] = relationship(
        back_populates='transaction',
        lazy='noload',
        cascade='save-update',
    )
