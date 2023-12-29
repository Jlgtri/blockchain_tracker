from asyncio import current_task
from logging import basicConfig, getLogger
from typing import Mapping, Optional

from aiogram import Bot
from aiohttp import ClientSession
from aiohttp_retry import ExponentialRetry, RetryClient
from asyncclick import command, option
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlalchemy.ext.asyncio.scoping import async_scoped_session
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.pool.impl import AsyncAdaptedQueuePool
from sqlalchemy.sql.ddl import DDL

try:
    from blockchain_tracker import BlockChainTracker
    from blockchain_tracker.models.base import Base
except ImportError:
    from src.blockchain_tracker import BlockChainTracker
    from src.blockchain_tracker.models.base import Base


@command(
    context_settings=dict(token_normalize_func=lambda x: x.strip().lower()),
)
@option(
    '-l',
    '--logging',
    help='The logging level used to display messges.',
    default='INFO',
)
@option(
    '-d',
    '--database-url',
    help='The *database_url* to use with SQLAlchemy.',
    required=True,
    envvar=['DATABASE_URL'],
    callback=lambda ctx, param, value: 'postgresql+asyncpg://'
    + value.split('://')[-1].split('?')[0].strip()
    if value
    else None,
)
@option(
    '-e',
    '--email',
    help='The email used to login at Tradersroom.',
    required=True,
)
@option(
    '-p',
    '--password',
    help='The password used to login at Tradersroom.',
    required=True,
)
@option(
    '-t',
    '--token',
    help='The Bot API *token* to create a Telegram bot session.',
    required=True,
)
@option(
    '-c',
    '--chat-id',
    type=int,
    help='The chat ID used to export transaction in Telegram.',
    required=True,
)
@option(
    '-h',
    '--headers',
    help='The *headers* to use at Tradersroom.',
    type=(str, str),
    multiple=True,
    callback=lambda ctx, param, value: dict(value),
)
async def cli(
    logging: Optional[str] = None,
    database_url: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    token: Optional[str] = None,
    chat_id: Optional[int] = None,
    headers: Optional[Mapping[str, str]] = None,
) -> None:
    basicConfig(level=logging, force=True)
    getLogger('sqlalchemy.engine.Engine').propagate = False
    Session = async_scoped_session(
        sessionmaker(
            engine := create_async_engine(
                echo=logging == 'DEBUG',
                url=database_url,
                poolclass=AsyncAdaptedQueuePool,
                pool_size=20,
                max_overflow=0,
                pool_recycle=3600,
                pool_pre_ping=True,
                pool_use_lifo=True,
                connect_args=dict(ssl=False, server_settings=dict(jit='off')),
                # execution_options=dict(isolation_level='SERIALIZABLE'),
            ),
            class_=AsyncSession,
            expire_on_commit=False,
            future=True,
        ),
        scopefunc=current_task,
    )
    try:
        async with engine.begin() as connection:
            for schema in {
                table.schema or 'public'
                for table in Base.metadata.tables.values()
            }:
                await connection.execute(
                    DDL(f'CREATE SCHEMA IF NOT EXISTS {schema}')
                )
            await connection.run_sync(Base.metadata.create_all)
        await BlockChainTracker(
            email,
            password,
            chat_id,
            Session,
            Bot(token),
            RetryClient(
                ClientSession(headers=headers),
                retry_options=ExponentialRetry(float('inf')),
            ),
            logger_name='BCT',
        ).run()
    except KeyboardInterrupt:
        pass
    finally:
        await engine.dispose()


if __name__ == '__main__':
    cli(auto_envvar_prefix='BCT')
