from typing import List, Optional

from pydantic import BaseModel

from server.core.enums import ChatRoomType
from server.core.externals.redis.mixin import SortedSetCollectionMixin, \
    SetCollectionMixin


class RedisFileBaseS(BaseModel):
    id: int
    url: str
    uid: str
    origin_uid: Optional[str] = None
    uploaded_by_id: Optional[int] = None
    filename: str
    filepath: str
    content_type: str
    use_type: str
    is_active: bool


class RedisUserImageFileS(RedisFileBaseS):
    user_profile_id: int
    type: str
    is_default: bool


class RedisChatHistoryFileS(RedisFileBaseS):
    chat_history_id: int
    order: int


class RedisUserProfileByRoomS(BaseModel):
    id: int
    nickname: str
    files: Optional[List[RedisUserImageFileS]] = []


class RedisChatHistoryByRoomS(BaseModel):
    id: int
    user_profile_id: int
    contents: Optional[str] = None
    files: Optional[List[RedisChatHistoryFileS]] = []
    read_user_ids: List[int] = []
    timestamp: float | int
    is_active: bool


class RedisChatRoomByUserProfileS(BaseModel):
    id: int
    name: str
    type: str
    user_profile_files: Optional[List[RedisUserImageFileS]] = []
    unread_msg_cnt: int


class RedisChatHistoryToSyncS(BaseModel):
    id: int


class RedisUserProfilesByRoomS(SetCollectionMixin):
    format = 'room:{}:user_profile:{}:user_profiles'
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
