from typing import TYPE_CHECKING

from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.sql.schema import CheckConstraint, Column
from sqlalchemy.sql.sqltypes import String

from ..._mixins import Timestamped
from ...base import Base

if TYPE_CHECKING:
    from ..transactions.transaction import Transaction


class Wallet(Timestamped, Base):
    address: Mapped[str] = Column(
        String(255),
        CheckConstraint("address <> ''"),
        primary_key=True,
    )
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
