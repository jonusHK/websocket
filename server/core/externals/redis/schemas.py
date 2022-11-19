from typing import List, Optional

from pydantic import BaseModel

from server.core.externals.redis.mixin import SortedSetCollectionMixin, \
    SetCollectionMixin


class RedisUserProfileByRoomS(BaseModel):
    id: int
    nickname: str
    # TODO RedisFileS 추가


class RedisFileS(BaseModel):
    id: int
    url: str
    is_default: bool


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
    unread_msg_cnt: int


class RedisChatHistoryToSyncS(BaseModel):
    id: int
    room_id: int
    user_profile_id: int


class RedisUserProfilesByRoomS(SetCollectionMixin):
    format = 'room:{}:user_profiles'
    schema = RedisUserProfileByRoomS


class RedisChatHistoriesByRoomS(SortedSetCollectionMixin):
    format = 'room:{}:chat_histories'
    schema = RedisChatHistoryByRoomS
    score = 'timestamp'


class RedisChatRoomsByUserProfileS(SetCollectionMixin):
    format = 'user:{}:chat_rooms'
    schema = RedisChatRoomByUserProfileS


class RedisChatHistoriesToSyncS(SortedSetCollectionMixin):
    format = 'update:chat_histories'
    schema = RedisChatHistoryToSyncS
    score = 'id'
