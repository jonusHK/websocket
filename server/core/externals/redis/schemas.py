from typing import List, Optional

from pydantic import BaseModel

from server.core.externals.redis.mixin import ListCollectionMixin, StringCollectionMixin


class RedisUserProfileByRoom(BaseModel):
    id: int
    nickname: str
    is_active: bool


class RedisChatHistoryByRoom(BaseModel):
    id: int
    user_profile_id: int
    contents: Optional[str] = None
    files: Optional[List[str]] = []
    read_user_ids: List[int] = []
    is_active: bool


class RedisChatRoomByUserProfile(BaseModel):
    id: int
    unread_msg_cnt: int


class RedisChatRoomDetail(StringCollectionMixin, BaseModel):
    format = 'room:{}'

    name: int
    is_active: bool


class RedisUserProfilesByRoom(ListCollectionMixin, BaseModel):
    format = 'room:{}:user_profiles'

    data: List[RedisUserProfileByRoom]


class RedisChatHistoriesByRoom(ListCollectionMixin, BaseModel):
    format = 'room:{}:chat_histories'

    data: List[RedisChatHistoryByRoom]


class RedisChatRoomsByUserProfile(ListCollectionMixin, BaseModel):
    format = 'user:{}:chat_rooms'

    data: List[RedisChatRoomByUserProfile]
