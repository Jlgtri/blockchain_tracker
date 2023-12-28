"""The module with the mixins for the mapped classes."""

from datetime import datetime
from typing import Self

from dateutil.tz.tz import tzlocal
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.decl_api import declared_attr
from sqlalchemy.sql.functions import now
from sqlalchemy.sql.schema import Column, FetchedValue
from sqlalchemy.sql.sqltypes import DateTime


class Timestamped(object):
    """Tracks timestamps when the instance was created and updated."""

    @declared_attr
    def created_at(self: Self, /) -> Mapped[datetime]:
        """Set the date and time when the instance was created."""
        return Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(tzlocal()),
            server_default=now(),
        )

    @declared_attr
    def updated_at(self: Self, /) -> Mapped[datetime]:
        """Set the date and time of the last time the instance was updated."""
        return Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(tzlocal()),
            server_default=now(),
            onupdate=lambda: datetime.now(tzlocal()),
            server_onupdate=FetchedValue(),
        )
