from enum import Enum, EnumMeta


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


class IntValueEnum(Enum, metaclass=IntValueEnumMeta):
    __default__ = None


class RelationshipType(IntValueEnum):
    FRIEND = "친구"
    FAMILY = "가족"

    __default__ = FRIEND


class ProfileImageType(IntValueEnum):
    PROFILE = "프로필 이미지"
    BACKGROUND = "배경 이미지"
