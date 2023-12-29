from typing import TYPE_CHECKING, Self

from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.sql.schema import CheckConstraint, Column
from sqlalchemy.sql.sqltypes import SmallInteger, String

from ..._mixins import Timestamped
from ...base import Base

if TYPE_CHECKING:
    from ..transactions.transaction import Transaction


class Token(Timestamped, Base):
    address: Mapped[str] = Column(
        String(255),
        CheckConstraint("address <> ''"),
        primary_key=True,
    )
    name: Mapped[str] = Column(
        String(63),
        CheckConstraint("name <> ''"),
        nullable=False,
    )
    symbol: Mapped[str] = Column(
        String(30),
        CheckConstraint("symbol <> ''"),
        nullable=False,
    )
    chain: Mapped[str] = Column(
        String(30),
        CheckConstraint("chain <> ''"),
        nullable=False,
    )
    decimals: Mapped[int] = Column(
        SmallInteger,
        CheckConstraint("decimals >= 0 AND decimals <= 18"),
        nullable=False,
    )

    transactions: Mapped['Transaction'] = relationship(
        back_populates='token',
        lazy='noload',
        cascade='save-update',
    )

    def format_amount(self: Self, amount: int, /) -> str:
        return '{:,g}'.format(amount / 10**self.decimals)
        try:
            frac_amount = amount / 10**self.decimals
            digits = -int(floor(log10(abs(modf(frac_amount)[0])))) + 1
            return ('{:,.%sf}' % digits).format(frac_amount)
        except ValueError:
            return '0.' + str(amount).zfill(self.decimals)
