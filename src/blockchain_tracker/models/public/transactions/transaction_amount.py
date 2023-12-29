from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.sql.schema import CheckConstraint, Column, ForeignKey
from sqlalchemy.sql.sqltypes import BigInteger, String

from ..._mixins import Timestamped
from ...base import Base
from .transaction import Transaction


class TransactionAmount(Timestamped, Base):
    transaction_hash: Mapped[str] = Column(
        Transaction.hash.type,
        ForeignKey(Transaction.hash, onupdate='RESTRICT', ondelete='CASCADE'),
        primary_key=True,
    )
    to_address: Mapped[str] = Column(
        String(255),
        CheckConstraint("to_address <> ''"),
        primary_key=True,
    )
    amount: Mapped[int] = Column(
        BigInteger,
        CheckConstraint('amount >= 0'),
        nullable=False,
    )

    transaction: Mapped['Transaction'] = relationship(
        back_populates='amounts',
        lazy='noload',
        cascade='save-update',
    )
