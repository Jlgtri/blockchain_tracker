from traceback import print_exc
from typing import Callable, ParamSpec, TypeVar

from anyio import get_cancelled_exc_class

#
T = TypeVar('T')
P = ParamSpec('P')


def wrap_exc(func: Callable[P, T], /) -> Callable[P, T]:
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await func(*args, **kwargs)
        except get_cancelled_exc_class():
            raise
        except BaseException as _:
            print_exc()
            raise

    return wrapper
