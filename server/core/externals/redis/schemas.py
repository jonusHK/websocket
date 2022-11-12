from typing import List, Optional

from pydantic import BaseModel

from server.core.externals.redis.mixin import ListCollectionMixin, StringCollectionMixin, SortedSetCollectionMixin


class RedisUserProfileByRoomS(BaseModel):
    id: int
    nickname: str
    is_active: bool


class RedisFileS(BaseModel):
    id: int
    url: str


class RedisChatHistoryByRoomS(BaseModel):
    id: int
    user_profile_id: int
    contents: Optional[str] = None
    files: Optional[List[RedisFileS]] = []
    read_user_ids: List[int] = []
    timestamp: int
    is_active: bool


class RedisChatRoomByUserProfileS(BaseModel):
    id: int
    unread_msg_cnt: int


class RedisChatRoomS(BaseModel):
    name: int
    is_active: bool


class RedisChatRoomDetailS(StringCollectionMixin, BaseModel):
    format = 'room:{}'
    schema = RedisChatRoomS


class RedisUserProfilesByRoomS(ListCollectionMixin):
    format = 'room:{}:user_profiles'
    schema = RedisUserProfileByRoomS


class RedisChatHistoriesByRoomS(SortedSetCollectionMixin):
    format = 'room:{}:chat_histories'
    schema = RedisChatHistoryByRoomS


class RedisChatRoomsByUserProfileS(ListCollectionMixin):
    format = 'user:{}:chat_rooms'
    schema = RedisChatRoomByUserProfileS
