from traceback import print_exc
from typing import Callable, Optional, ParamSpec, TypeVar

from anyio import get_cancelled_exc_class
from sqlalchemy.ext.asyncio.scoping import async_scoped_session

#
T = TypeVar('T')
P = ParamSpec('P')


def wrap_exc(
    func: Callable[P, T],
    /,
    Session: Optional[async_scoped_session] = None,
) -> Callable[P, T]:
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await func(*args, **kwargs)
        except get_cancelled_exc_class():
            raise
        except BaseException as _:
            print_exc()
            if Session is not None:
                await Session.remove()
            raise

    return wrapper
