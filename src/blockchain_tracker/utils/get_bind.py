from typing import Tuple, Union

from sqlalchemy.engine.base import Connection, Engine
from sqlalchemy.ext.asyncio.engine import AsyncConnection, AsyncEngine
from sqlalchemy.ext.asyncio.scoping import async_scoped_session
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import Session as SyncSession
from sqlalchemy.orm.session import sessionmaker

Bind = Union[
    Union[sessionmaker, scoped_session, SyncSession, Connection, Engine],
    async_scoped_session,
    AsyncSession,
    AsyncConnection,
    AsyncEngine,
]


def get_bind(
    bind: Bind,
) -> Tuple[
    Union[Engine, AsyncEngine],
    Union[
        None,
        sessionmaker[SyncSession],
        scoped_session[SyncSession],
        async_scoped_session[SyncSession],
        sessionmaker[AsyncSession],
        scoped_session[AsyncSession],
        async_scoped_session[AsyncSession],
    ],
]:
    Session = None
    while not isinstance(bind, (Engine, AsyncEngine)):
        if isinstance(bind, (scoped_session, async_scoped_session)):
            if Session is None:
                Session = bind
            bind = bind.session_factory
        elif isinstance(bind, sessionmaker):
            if Session is None:
                Session = bind
            bind = bind.kw['bind']
        elif isinstance(bind, (SyncSession, AsyncSession)):
            bind = bind.bind
        elif isinstance(bind, (Connection, AsyncConnection)):
            bind = bind.engine
        else:
            raise ValueError(f'Invalid bind: {bind}')
    return bind, Session
