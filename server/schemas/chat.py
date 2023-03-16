from typing import Optional, List

from pydantic import BaseModel, validator, root_validator

from server.core.enums import ChatType, ChatRoomType


class ChatRoomCreateParamS(BaseModel):
    user_profile_id: int
    target_profile_ids: List[int]
    type: Optional[int] = ChatRoomType.PUBLIC.value

    @validator('type', always=True)
    def validate_type(cls, value: str | None):
        if value:
            enum = ChatRoomType(value)
            if enum is None:
                raise ValueError('Invalid type.')
            return enum
        return value


class ChatReceiveFileS(BaseModel):
    content: str
    content_type: str
    filename: str


class ChatReceiveDataS(BaseModel):
    text: Optional[str] = None
    history_redis_ids: Optional[List[str]] = None
    target_profile_ids: Optional[List[int]] = None
    files: Optional[list[ChatReceiveFileS]] = None
    is_read: Optional[bool] = None
    offset: Optional[int] = None
    limit: Optional[int] = None
    exit: Optional[bool] = None
    timestamp: Optional[float | int] = None
    is_active: bool = True


class ChatSendDataS(BaseModel):
    from server.core.externals.redis.schemas import (
        RedisChatHistoryByRoomS,
        RedisChatHistoryPatchS,
        RedisUserProfileByRoomS,
        RedisChatRoomListS,
        RedisFollowingByUserProfileS
    )

    history: Optional[RedisChatHistoryByRoomS] = None
    histories: Optional[List[RedisChatHistoryByRoomS]] = None
    patch_histories: Optional[List[RedisChatHistoryPatchS]] = None
    user_profiles: Optional[List[RedisUserProfileByRoomS]] = None
    rooms: Optional[List[RedisChatRoomListS]] = None
    followings: Optional[List[RedisFollowingByUserProfileS]] = None
    pong: Optional[bool] = None


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
