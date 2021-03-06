import bcrypt
from pytz import timezone
from sqlalchemy.types import TypeDecorator
from sqlalchemy import Integer


class IntTypeEnum(TypeDecorator):
    """Store IntEnum as Integer"""

    impl = Integer

    def __init__(self, *args, **kwargs):
        self.enum_class = kwargs.pop('enum_class')
        TypeDecorator.__init__(self, *args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not isinstance(value, self.enum_class):
                raise TypeError("value should %s type" % self.enum_class)
            return value.value

    def process_result_value(self, value, dialect):
        if value is not None:
            if not isinstance(value, int):
                raise TypeError("value should have int type")
            return self.enum_class(value)


def get_tz(tz='Asia/Seoul'):
    return timezone(tz)


def hash_password(target: str) -> bytes:
    return bcrypt.hashpw(target.encode('utf-8'), bcrypt.gensalt())


def check_password(t1: str, t2: str) -> bool:
    return bcrypt.checkpw(t1.encode('utf-8'), t2.encode('utf-8'))
