from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, validator

from server.core.enums import ProfileImageType, RelationshipType, FollowType, ResponseCode
from server.core.exceptions import ClassifiableException
from server.core.utils import get_formatted_phone, get_phone
from server.schemas import ConvertMixinS
from server.schemas.base import S3MediaBaseS


class UserBase(BaseModel):
    uid: str
    name: str
    mobile: str
    email: str
    is_superuser: bool = False
    is_staff: bool = False
    is_active: bool = True


class UserCreateS(UserBase):
    uid: Optional[str] = None
    password: str

    @validator('mobile')
    def validate_mobile(cls, value: str):
        try:
            return get_formatted_phone(get_phone(value), with_country=True, raise_exception=True)
        except ValueError:
            raise ClassifiableException(code=ResponseCode.INVALID_MOBILE)


class UserS(UserBase):
    id: int
    last_login: Optional[datetime] = None
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserRelationshipBaseS(BaseModel):
    other_profile_nickname: str
    type: RelationshipType
    favorites: bool = False
    is_hidden: bool = False
    is_forbidden: bool = False


class UserRelationshipUpdateS(ConvertMixinS, BaseModel):
    other_profile_nickname: Optional[str] = None
    type: Optional[int] = None
    favorites: Optional[bool] = None
    is_hidden: Optional[bool] = None
    is_forbidden: Optional[bool] = None

    @validator('type')
    def get_type(cls, v: int):
        enum = RelationshipType(v)
        if not enum:
            raise ValueError('Invalid `type` value.')
        return enum


class UserRelationshipS(UserRelationshipBaseS):
    id: int
    my_profile_id: int
    other_profile_id: int

    class Config:
        orm_mode = True


class UserProfileImageBaseS(S3MediaBaseS):
    type: ProfileImageType
    user_profile_id: int
    is_default: bool = False
    is_active: bool = True


class UserProfileImageCreateS(UserProfileImageBaseS):
    pass


class UserProfileImageS(UserProfileImageBaseS):
    id: int
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserProfileImageUploadS(BaseModel):
    user_profile_id: int
    image_type: str
    is_default: bool


class UserProfileBaseS(BaseModel):
    user_id: int
    identity_id: str
    nickname: str
    status_message: Optional[str] = None
    is_default: bool = False
    is_active: bool = True


class UserProfileS(UserProfileBaseS):
    id: int
    images: Optional[List[UserProfileImageS]] = []
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserProfileSearchS(ConvertMixinS, BaseModel):
    id: Optional[int] = None
    identity_id: Optional[str] = None
    nickname: Optional[str] = None


class UserProfileSearchImageS(BaseModel):
    id: int
    url: str
    type: ProfileImageType
    is_default: bool
    is_active: bool


class UserProfileSearchResponseS(BaseModel):
    id: int
    user_id: int
    identity_id: str
    nickname: str
    status_message: Optional[str] = None
    images: Optional[List[UserProfileSearchImageS]] = []
    is_default: bool
    is_active: bool


class UserRelationshipSearchS(ConvertMixinS, BaseModel):
    nickname: Optional[str] = None
    follow_type: Optional[int] = None
    relationship_type: Optional[int] = None
    favorites: Optional[bool] = None
    is_hidden: Optional[bool] = None
    is_forbidden: Optional[bool] = None

    @validator('follow_type')
    def validate_follow_type(cls, value: int | None):
        if value:
            enum = FollowType(value)
            if not enum:
                raise ValueError('Invalid `follow_type`.')
            return enum
        return value

    @validator('relationship_type')
    def validate_relationship_type(cls, value: int | None):
        if value:
            enum = RelationshipType(value)
            if not enum:
                raise ValueError('Invalid `relationship_type`.')
            return enum
        return value


class UserRelationshipSearchResponseS(BaseModel):
    id: int
    profile: UserProfileSearchResponseS
    type: RelationshipType
    favorites: bool
    is_hidden: bool
    is_forbidden: bool


class UserSessionBaseS(BaseModel):
    user_id: int
    session_id: str
    expiry_at: datetime


class UserSessionCreateS(UserSessionBaseS):
    pass


class UserSessionS(UserSessionBaseS):
    id: int
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LoginUserS(BaseModel):
    user: UserS
    profile: Optional[UserProfileS] = None
