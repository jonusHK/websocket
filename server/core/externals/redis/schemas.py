from typing import List, Optional

from pydantic import BaseModel

from server.core.externals.redis.mixin import ListCollectionMixin, StringCollectionMixin, SortedSetCollectionMixin


class RedisUserProfileByRoomS(BaseModel):
    id: int
    nickname: str
    is_active: bool
    # TODO RedisFileS 추가


class RedisFileS(BaseModel):
    id: int
    url: str
    is_default: bool
    is_active: bool


class RedisChatHistoryByRoomS(BaseModel):
    id: int
    user_profile_id: int
    contents: Optional[str] = None
    files: Optional[List[RedisFileS]] = []
    read_user_ids: List[int] = []
    timestamp: float | int
    is_active: bool


class RedisChatRoomByUserProfileS(BaseModel):
    id: int
    name: str
    is_active: bool
    unread_msg_cnt: int


class RedisChatRoomS(BaseModel):
    name: str
    is_active: bool


class RedisChatHistoryToSyncS(BaseModel):
    id: int
    room_id: int
    user_profile_id: int


class RedisChatRoomDetailS(StringCollectionMixin):
    format = 'room:{}'
    schema = RedisChatRoomS


class RedisUserProfilesByRoomS(ListCollectionMixin):
    format = 'room:{}:user_profiles'
    schema = RedisUserProfileByRoomS


class RedisChatHistoriesByRoomS(SortedSetCollectionMixin):
    format = 'room:{}:chat_histories'
    schema = RedisChatHistoryByRoomS
    score = 'timestamp'


class RedisChatRoomsByUserProfileS(ListCollectionMixin):
    format = 'user:{}:chat_rooms'
    schema = RedisChatRoomByUserProfileS


class RedisChatHistoriesToSyncS(SortedSetCollectionMixin):
    format = 'update:chat_histories'
    schema = RedisChatHistoryToSyncS
    score = 'id'
