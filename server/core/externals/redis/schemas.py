from typing import List, Optional

from pydantic import BaseModel

from server.core.externals.redis.mixin import SortedSetCollectionMixin, \
    SetCollectionMixin


class RedisFileS(BaseModel):
    id: int
    user_profile_id: int
    url: str
    type: str
    is_default: bool
    is_active: bool


class RedisUserProfileByRoomS(BaseModel):
    id: int
    nickname: str
    files: Optional[List[RedisFileS]] = []


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
    user_profile_files: Optional[List[RedisFileS]] = []
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
    score = 'timestamp'  # schema 내부 필드여야 함


class RedisChatRoomsByUserProfileS(SetCollectionMixin):
    format = 'user:{}:chat_rooms'
    schema = RedisChatRoomByUserProfileS


class RedisChatHistoriesToSyncS(SortedSetCollectionMixin):
    format = 'update:chat_histories'
    schema = RedisChatHistoryToSyncS
    score = 'id'  # schema 내부 필드여야 함
