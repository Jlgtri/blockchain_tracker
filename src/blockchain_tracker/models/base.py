from re import findall
from typing import ClassVar, Dict, Final, Self, Tuple, Type, Union

from inflect import engine
from sqlalchemy.orm.decl_api import declarative_base, declared_attr
from sqlalchemy.sql.schema import SchemaItem


class BaseInterface(object):
    """The base class for all :module:`SQLAlchemy` models."""

    _inflect: ClassVar[engine] = engine()
    __mapper_args__: ClassVar[Dict[str, object]] = dict(eager_defaults=True)

    @declared_attr.directive
    @classmethod
    def __tablename__(cls: Type[Self], /) -> str:
        words = findall(r'[A-Z]+[^A-Z]*', cls.__name__.removesuffix('Model'))
        words.append(cls._inflect.plural(words.pop().lower()))
        return '_'.join(word.lower() for word in words)


TableArgs = Tuple[Union[SchemaItem, Dict[str, object]]]
Base: Final[Type[BaseInterface]] = declarative_base(cls=BaseInterface)
