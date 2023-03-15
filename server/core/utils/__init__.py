import random
import re
import string
from typing import Iterable

import phonenumbers
from passlib.context import CryptContext
from phonenumbers.phonenumber import PhoneNumber as BasePhoneNumber
from sqlalchemy import Integer
from sqlalchemy.types import TypeDecorator
from sqlalchemy_utils import PhoneNumber, PhoneNumberParseException

from server.core.constants import REGION_CODES


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


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> bytes:
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def validate_region(region):
    if (
        region is not None
        and region not in REGION_CODES
    ):
        raise ValueError(
            "`%s` is not a valid region code. Choices are %r"
            % (region, REGION_CODES)
        )


def get_formatted_phone(parsed_value: PhoneNumber, with_country=False, with_hyphen=False, raise_exception=False) -> str:
    is_valid = True
    while not parsed_value.is_valid_number():
        # 010 뒤 0 으로 시작하는 경우, is_valid_number = False 로 리턴되는 현상 대응
        if (
            parsed_value.region == 'KR'
            and 9 <= len(str(parsed_value.national_number)) <= 10
            and str(parsed_value.national_number).startswith('100')
        ):
            break

        is_valid = False
        if raise_exception:
            raise ValueError('Invalid phone number.')
        break

    if is_valid:
        if with_country:
            # INTERNATIONAL -> +82 10-1234-5678, E164 -> +821086075857
            attr = 'INTERNATIONAL' if with_hyphen else 'E164'
            fmt = getattr(phonenumbers.PhoneNumberFormat, attr)
        else:
            # NATIONAL -> 010-1234-5857
            fmt = phonenumbers.PhoneNumberFormat.NATIONAL
        value = phonenumbers.format_number(parsed_value, fmt)
    else:
        value = parsed_value.raw_input

    if not with_hyphen:
        value = re.sub(r'-', '', value)

    return value


def get_phone(value: str, region='KR') -> PhoneNumber:
    validate_region(region)

    if not value:
        phone_number = value
    elif isinstance(value, str):
        try:
            phone_number = PhoneNumber(raw_number=value, region=region)
        except PhoneNumberParseException:
            phone_number = BasePhoneNumber(raw_input=value)
    elif isinstance(value, PhoneNumber):
        phone_number = value
    elif isinstance(value, phonenumbers.PhoneNumber):
        phone_number = PhoneNumber()
        phone_number.merge_from(value)
    else:
        raise TypeError("Can't convert %s to PhoneNumber." % type(value).__name__)

    return phone_number


def generate_random_string(
    words=string.digits + string.ascii_letters,
    length=10
):
    random_str = ''
    for _ in range(length):
        random_str += random.choice(words)
    return random_str


async def async_iter(iterable: Iterable):
    for v in iterable:
        yield v
