from typing import Final

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import BigInteger, Integer

from ..._mixins import Timestamped
from ...base import Base, TableArgs
from ...public.transactions.transaction import Transaction


class ChatMessage(Timestamped, Base):
    """The model of a Pyrogram peer."""

    chat_id: Mapped[int] = Column(BigInteger, primary_key=True)
    message_id: Mapped[int] = Column(
        Integer,
        CheckConstraint('message_id > 0'),
        primary_key=True,
    )
    transaction_hash: Mapped[str] = Column(
        Transaction.hash.type,
        ForeignKey(
            Transaction.hash,
            onupdate='RESTRICT',
            ondelete='NO ACTION',
        ),
        nullable=False,
    )

    transaction: Mapped['Transaction'] = relationship(
        back_populates='telegram_chat_messages',
        lazy='noload',
        cascade='save-update',
    )

    __table_args__: Final[TableArgs] = (dict(schema='tg'),)
