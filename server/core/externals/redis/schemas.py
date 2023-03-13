from typing import List, Optional, Iterable, Dict, Any

from pydantic import BaseModel

from server.core.enums import IntValueEnum
from server.core.externals.redis.mixin import (
    SortedSetCollectionMixin, SetCollectionMixin, HashCollectionMixin, ScanMixin, KeyMixin
)
from server.models import S3Media, UserProfileImage, ChatHistoryFile, UserProfile, ChatHistory


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

    _model = None

    @classmethod
    async def generate_files_schema(
        cls,
        iterable: Iterable,
        presigned=False
    ) -> list:
        assert issubclass(cls._model, S3Media), 'Invalid model type.'

        files_s: List[cls] = []
        if iterable:
            urls: List[Dict[str, Any]] = (
                await cls._model.asynchronous_presigned_url(*iterable)
                if presigned
                else cls._model.get_file_urls(*iterable)
            )
            for m in iterable:
                model_to_dict = m.to_dict()
                model_to_dict.update({
                    'url': next((u['url'] for u in urls if u['id'] == m.id), None)
                })

                for k, v in cls.__annotations__.items():
                    if type(model_to_dict[k]) is not v:
                        if isinstance(model_to_dict[k], IntValueEnum):
                            if v is str:
                                model_to_dict[k] = model_to_dict[k].name.lower()
                            elif v is int:
                                model_to_dict[k] = model_to_dict[k].value
                files_s.append(cls(**model_to_dict))

        return files_s


class RedisUserImageFileS(RedisFileBaseS):
    user_profile_id: int
    type: str
    is_default: bool

    _model = UserProfileImage

    @classmethod
    async def generate_profile_images_schema(
        cls,
        profiles: List[UserProfile],
        only_default=False
    ) -> list:
        images: List[cls._model] = []
        for p in profiles:
            assert hasattr(p, 'images'), 'Profile must have `images` attr.'
            if only_default:
                image = next((im for im in p.images if im.is_default), None)
                if image:
                    images.append(image)
            else:
                for image in p.images:
                    images.append(image)
        return await cls.generate_files_schema(images)


class RedisChatHistoryFileS(RedisFileBaseS):
    chat_history_id: int
    order: int

    _model = ChatHistoryFile


class RedisUserProfileS(BaseModel):
    id: int
    identity_id: str
    nickname: str
    image: Optional[RedisUserImageFileS] = None
    files: List[RedisUserImageFileS] = []


class RedisFollowingS(RedisUserProfileS):
    type: str
    favorites: bool
    is_hidden: bool
    is_forbidden: bool


class RedisUserProfileByRoomS(RedisUserProfileS):
    ...

    @classmethod
    def get_default_room_name(cls, user_profile_id: int, profiles: List['RedisUserProfileByRoomS']):
        if not profiles:
            return

        profiles.sort(key=lambda x: x.nickname)
        if len(profiles) == 2:
            room_name = next(
                (p.nickname for p in profiles if p.id != user_profile_id),
                None
            )
        else:
            room_name: str = ', '.join([p.nickname for p in profiles])
        return room_name


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
    files: List[RedisChatHistoryFileS] = []
    read_user_ids: List[int] = []
    timestamp: float | int
    date: str
    is_active: bool

    @classmethod
    async def from_model(cls, model: ChatHistory):
        assert hasattr(model, 'user_profile_mapping'), 'Must have `user_profile_mapping` attr.'
        return cls(
            id=model.id,
            redis_id=model.redis_id,
            user_profile_id=model.user_profile_id,
            type=model.type.name.lower(),
            files=await RedisChatHistoryFileS.generate_files_schema(
                model.files, presigned=True
            ),
            read_user_ids=[
                m.user_profile_id for m in getattr(model, 'user_profile_mapping') if m.is_read
            ],
            timestamp=model.created.timestamp(),
            date=model.created.date().isoformat(),
            is_active=model.is_active
        )


class RedisChatRoomInfoS(BaseModel):
    id: int
    type: str
    user_profile_ids: List[int] = []
    user_profile_files: List[RedisUserImageFileS] = []
    connected_profile_ids: List[int] = []

    def add_connected_profile_id(self, profile_id: int):
        if profile_id not in self.connected_profile_ids:
            self.connected_profile_ids.append(profile_id)


class RedisChatRoomByUserProfileS(BaseModel):
    id: int
    name: str | None = None
    unread_msg_cnt: int
    timestamp: float | int


class RedisChatRoomListS(RedisChatRoomByUserProfileS):
    type: Optional[str] = None
    user_profiles: List[RedisUserProfileByRoomS]
    user_profile_files: List[RedisUserImageFileS] = []
    last_chat_history: Optional[RedisChatHistoryByRoomS] = None
    last_chat_timestamp: Optional[float] = None


class RedisChatHistoryToSyncS(BaseModel):
    id: int


class RedisFollowingByUserProfileS(RedisFollowingS):
    ...


class RedisInfoByRoomS(HashCollectionMixin, ScanMixin):
    format = 'room:{}:info'
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


class RedisChatRoomPubSubS(KeyMixin):
    format = 'pubsub:room:{}:chat'
