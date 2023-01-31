from typing import Optional, List

from pydantic import BaseModel, validator, root_validator

from server.core.enums import ChatType, ChatRoomType


class ChatRoomCreateParamS(BaseModel):
    user_profile_id: int
    target_profile_ids: List[int]
    type: str

    @classmethod
    def convert_type(cls, value):
        enum = None
        if isinstance(value, ChatRoomType):
            enum = value
        elif isinstance(value, str):
            enum = ChatRoomType.get_by_name(value)
        elif isinstance(value, int):
            enum = ChatRoomType(value)

        if enum is None:
            raise ValueError('Invalid type.')
        return enum

    @root_validator
    def validate_all(cls, values):
        room_type = cls.convert_type(values['type'])
        values.update({'type': room_type})
        return values


class ChatReceiveFileS(BaseModel):
    content: str
    content_type: str
    filename: str


class ChatReceiveDataS(BaseModel):
    text: Optional[str] = None
    history_ids: Optional[List[int]] = None
    target_profile_ids: Optional[List[int]] = None
    files: Optional[list[ChatReceiveFileS]] = None
    is_read: Optional[bool] = None
    offset: Optional[int] = None
    limit: Optional[int] = None
    timestamp: Optional[float | int] = None
    is_active: bool = True


class ChatSendDataS(BaseModel):
    from server.core.externals.redis.schemas import RedisChatHistoryByRoomS, RedisChatHistoryPatchS

    history: Optional[RedisChatHistoryByRoomS] = None
    histories: Optional[List[RedisChatHistoryByRoomS]] = None
    patch_histories: Optional[List[RedisChatHistoryPatchS]] = None


class ChatReceiveFormS(BaseModel):
    type: str
    data: Optional[ChatReceiveDataS] = None

    @validator("type")
    def get_type(cls, v):
        if v not in (e.name.lower() for e in ChatType):
            raise ValueError("Invalid `type` value.")
        return ChatType.get_by_name(v)


class ChatSendFormS(BaseModel):
    type: ChatType
    data: ChatSendDataS

    @validator("type")
    def get_type(cls, v):
        if v not in ChatType:
            raise ValueError("Invalid `type` value.")
        return v.name.lower()
