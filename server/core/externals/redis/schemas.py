from typing import List, Optional

from pydantic import BaseModel

from server.core.externals.redis.mixin import SortedSetCollectionMixin, SetCollectionMixin


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


class RedisUserProfileS(BaseModel):
    id: int
    identity_id: str
    nickname: str
    image: Optional[RedisUserImageFileS] = None
    files: Optional[List[RedisUserImageFileS]] = []


class RedisFollowingS(RedisUserProfileS):
    type: str
    favorites: bool
    is_hidden: bool
    is_forbidden: bool


class RedisUserProfileByRoomS(RedisUserProfileS):
    ...


class RedisChatHistoryPatchS(BaseModel):
    id: Optional[int] = None
    redis_id: str
    user_profile_id: int
    is_active: bool
    read_user_ids: List[int] = []


class RedisChatHistoryByRoomS(BaseModel):
    id: Optional[int] = None
    redis_id: str
    user_profile_id: int
    contents: Optional[str] = None
    type: str
    files: Optional[List[RedisChatHistoryFileS]] = []
    read_user_ids: List[int] = []
    timestamp: float | int
    date: str
    is_active: bool


class RedisChatRoomInfoS(BaseModel):
    id: int
    type: str
    user_profile_ids: List[int]
    user_profile_files: Optional[List[RedisUserImageFileS]] = []


class RedisChatRoomByUserProfileS(BaseModel):
    id: int
    name: str | None = None
    unread_msg_cnt: int
    timestamp: float | int


class RedisChatHistoryToSyncS(BaseModel):
    id: int


class RedisFollowingByUserProfileS(RedisFollowingS):
    ...


class RedisChatRoomsInfoS(SetCollectionMixin):
    format = 'rooms'
    schema = RedisChatRoomInfoS


class RedisUserProfilesByRoomS(SetCollectionMixin):
    format = 'room:{}:user_profile:{}:user_profiles'
    schema = RedisUserProfileByRoomS


class RedisChatHistoriesByRoomS(SortedSetCollectionMixin):
    format = 'room:{}:chat_histories'
    schema = RedisChatHistoryByRoomS
    score = 'timestamp'  # schema 내부 필드여야 함


class RedisChatRoomsByUserProfileS(SortedSetCollectionMixin):
    format = 'user:{}:chat_rooms'
    schema = RedisChatRoomByUserProfileS
    score = 'timestamp'  # schema 내부 필드여야 함


class RedisChatHistoriesToSyncS(SortedSetCollectionMixin):
    format = 'update:chat_histories'
    schema = RedisChatHistoryToSyncS
    score = 'id'  # schema 내부 필드여야 함


class RedisFollowingsByUserProfileS(SetCollectionMixin):
    format = 'user:{}:followings'
    schema = RedisFollowingByUserProfileS
