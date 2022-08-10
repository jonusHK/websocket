from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, Text, ForeignKey
from sqlalchemy.orm import relationship

from server.core.enums import RelationshipType, ProfileImageType
from server.core.utils import IntTypeEnum
from server.databases import Base
from server.models.base import TimestampMixin, S3Media


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    uid = Column(String(30), nullable=False)
    password = Column(String(150), nullable=False)
    name = Column(String(30), nullable=False)
    mobile = Column(String(30), unique=True, nullable=False)
    email = Column(String(50), unique=True, nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_staff = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    profiles = relationship("UserProfile", back_populates="user")


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    nickname = Column(String(30), nullable=False)
    status_message = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="profiles")
    images = relationship("UserProfileImage", back_populates="profile", cascade="all, delete-orphan")
    rooms = relationship("ChatRoomUserAssociation", back_populates="user_profile", cascade="all, delete", passive_deletes=True)


class UserRelationship(Base):
    __tablename__ = "user_relationships"

    id = Column(BigInteger, primary_key=True, index=True)
    my_profile_id = Column(BigInteger, ForeignKey("user_profiles.id"), nullable=False)
    other_profile_id = Column(BigInteger, ForeignKey("user_profiles.id"), nullable=False)
    type = Column(IntTypeEnum(enum_class=RelationshipType), default=RelationshipType.FRIEND, nullable=False)
    favorites = Column(Boolean, default=False, nullable=False)
    is_hidden = Column(Boolean, default=False, nullable=False)
    is_forbidden = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    my_profile = relationship("UserProfile", foreign_keys=[my_profile_id])
    other_profile = relationship("UserProfile", foreign_keys=[other_profile_id])


class UserProfileImage(S3Media):
    __tablename__ = "user_profile_images"

    id = Column(BigInteger, ForeignKey('s3_media.id'), primary_key=True)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id", on_delete="cascade"), nullable=False)
    type = Column(IntTypeEnum(enum_class=ProfileImageType), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    profile = relationship("UserProfile", back_populates="images")

    __mapper_args__ = {
        "polymorphic_identity": "user_profile_image"
    }


class UserSession(TimestampMixin, Base):
    __tablename__ = "user_sessions"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    session_id = Column(String(150), nullable=False)
    expiry_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="sessions")
