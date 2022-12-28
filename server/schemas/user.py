from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, validator

from server.core.enums import ProfileImageType, RelationshipType
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
    type: Optional[str] = None
    favorites: Optional[bool] = None
    is_hidden: Optional[bool] = None
    is_forbidden: Optional[bool] = None

    @validator("type")
    def get_type(cls, v):
        enum = RelationshipType.get_by_name(v)
        if not enum:
            raise ValueError("Invalid `type` value.")
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
