from enum import Enum, EnumMeta


class ResponseCode(Enum):
    OK = '정상적으로 처리됐습니다.'
    INVALID = '유효하지 않은 요청입니다.'
    UNAUTHORIZED = '유효한 인증 자격 증명이 없습니다.'
    INVALID_TOKEN = '유효하지 않은 토큰입니다.'
    TOKEN_EXPIRED = '토큰이 만료됐습니다.'
    PERMISSION_DENIED = '권한이 없습니다.'
    NOT_FOUND = '요청한 데이터가 존재하지 않습니다.'
    METHOD_NOT_ALLOWED = '허용되지 않은 메소드입니다.'
    NOT_ALLOWED = '허용되지 않은 작업입니다.'
    INVALID_JSON_FORMAT = '유효한 JSON 포맷이 아닙니다.'
    INVALID_UID = '유효한 UID가 아닙니다.'
    INVALID_USER_NAME = '유효한 이름이 아닙니다.'
    INVALID_MOBILE = '유효한 휴대폰 번호가 아닙니다.'
    INVALID_PASSWORD = '유효한 비밀번호가 아닙니다.'
    ALREADY_SIGNED_UP = '이미 회원가입 되어 있습니다.'
    INTERNAL_SERVER_ERROR = '정의되지 않은 오류'

    def retrieve(self):
        return {'code': self.name, 'message': self.value}


class IntValueEnumMeta(EnumMeta):
    def __new__(mcs, cls, bases, classdict):
        choices, names, i, default = [], [], 1, None
        for k, v in classdict.items():
            if k in ['_generate_next_value_', '__module__', '__qualname__', '__default__'] or not isinstance(v, str):
                continue
            choices.append((i, v))
            names.append(k)
            if '__default__' in classdict and classdict['__default__'] and classdict['__default__'] == v:
                default = i
            classdict.update({k: i})
            i += 1

        enum_class = super().__new__(mcs, cls, bases, classdict)
        enum_class._choices = tuple(choices)
        enum_class.choices = lambda: enum_class._choices
        enum_class._names = tuple(names)
        enum_class.names = lambda: enum_class._names
        enum_class._mapper = {}
        for e, (_, v) in zip(enum_class, enum_class._choices):
            enum_class._mapper[e] = v
        if default:
            enum_class.__default__ = enum_class(default)

        return enum_class

    def __getitem__(self, item):
        mapper = self._mapper
        try:
            return mapper.get(item, mapper.get(self(item), ''))
        except ValueError:
            return ''

    def get_by_name(cls, name):
        return next((e for e, v in cls._mapper.items() if e.name == name.upper()), None)


class IntValueEnum(Enum, metaclass=IntValueEnumMeta):
    __default__ = None


class RelationshipType(IntValueEnum):
    FRIEND = "친구"
    FAMILY = "가족"

    __default__ = FRIEND


class ProfileImageType(IntValueEnum):
    PROFILE = "프로필 이미지"
    BACKGROUND = "배경 이미지"


class UserType(IntValueEnum):
    USER = "유저"
    ADMIN = "관리자"
    SUPERUSER = "마스터 관리자"


class ChatType(IntValueEnum):
    MESSAGE = "메시지"
    FILE = "파일"
    UPDATE = "변경"
    INVITE = "초대"
    LOOKUP = "조회"


class ChatRoomType(IntValueEnum):
    ONE_TO_ONE = "개인"
    GROUP = "단체"
