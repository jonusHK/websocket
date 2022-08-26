from datetime import datetime
from typing import List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship

from server.core.enums import RelationshipType, ProfileImageType
from server.core.utils import IntTypeEnum
from server.models.base import TimestampMixin, S3Media, SQLModel


class User(SQLModel, TimestampMixin, table=True):
    __tablename__ = "users"

    id: int = Field(primary_key=True, index=True)
    uid: str = Field(max_length=30)
    password: str = Field(max_length=150)
    name: str = Field(max_length=30)
    mobile: str = Field(max_length=30)
    email: str = Field(max_length=50)
    last_login: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True))
    is_staff: bool = Field(default=False)
    is_superuser: bool = Field(default=False)
    is_active: bool = Field(default=True)

    profiles: List["UserProfile"] = Relationship(back_populates="user")
    sessions: List["UserSession"] = Relationship(back_populates="user")


class UserProfile(SQLModel, TimestampMixin, table=True):
    __tablename__ = "user_profiles"

    id: int = Field(sa_column=sa.Column(sa.BigInteger, primary_key=True, index=True))
    user_id: int = Field(sa_column=sa.Column(sa.BigInteger), foreign_key="users.id")
    nickname: str = Field(max_length=30)
    status_message: str = Field(sa_column=sa.Column(sa.Text, nullable=True))
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)

    user: User = Relationship(back_populates="profiles")
    images: List[Optional["UserProfileImage"]] = Relationship(
        sa_relationship=relationship(
            "UserProfileImage", back_populates="profile", cascade="all, delete-orphan"))
    rooms: List[Optional["ChatRoomUserAssociation"]] = Relationship(
        sa_relationship=relationship(
            "ChatRoomUserAssociation", back_populates="user_profile", cascade="all, delete", passive_deletes=True))


class UserRelationship(SQLModel, table=True):
    __tablename__ = "user_relationships"

    id: int = Field(sa_column=sa.Column(sa.BigInteger, primary_key=True, index=True))
    my_profile_id: int = Field(sa_column=sa.Column(sa.BigInteger), foreign_key="user_profiles.id")
    other_profile_id: int = Field(sa_column=sa.Column(sa.BigInteger, foreign_key="user_profiles.id"))
    type: IntTypeEnum = Field(
        sa_column=sa.Column(IntTypeEnum(enum_class=RelationshipType), default=RelationshipType.FRIEND))
    # type = Column(IntTypeEnum(enum_class=RelationshipType), default=RelationshipType.FRIEND, nullable=False)
    favorites: bool = Field(default=False)
    is_hidden: bool = Field(default=False)
    is_forbidden: bool = Field(default=False)
    is_active: bool = Field(default=True)

    my_profile = Relationship(sa_relationship=relationship("UserProfile", foreign_keys=[my_profile_id]))
    other_profile = Relationship(sa_relationship=relationship("UserProfile", foreign_keys=[other_profile_id]))


class UserProfileImage(S3Media):
    __tablename__ = "user_profile_images"

    id: int = Field(sa_column=sa.Column(sa.BigInteger), foreign_key="s3_media.id", primary_key=True)
    user_profile_id: int = Field(sa_column=sa.Column(sa.BigInteger), foreign_key="user_profiles.id")
    type: IntTypeEnum = Field(sa_column=sa.Column(IntTypeEnum(enum_class=ProfileImageType)))
    # type = Column(IntTypeEnum(enum_class=ProfileImageType), nullable=False)
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)

    profile: UserProfile = Relationship(back_populates="images")

    __mapper_args__ = {
        "polymorphic_identity": "user_profile_image"
    }


class UserSession(SQLModel, TimestampMixin, table=True):
    __tablename__ = "user_sessions"

    id: int = Field(sa_column=sa.Column(sa.BigInteger, primary_key=True, index=True))
    user_id: int = Field(sa_column=sa.Column(sa.BigInteger), foreign_key="users.id")
    session_id: int = Field(max_length=150)
    expiry_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True)))

    user: User = Relationship(back_populates="sessions")
