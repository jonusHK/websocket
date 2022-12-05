from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, Text, ForeignKey
from sqlalchemy.orm import relationship

from server.core.enums import RelationshipType, ProfileImageType
from server.core.utils import IntTypeEnum
from server.db.databases import Base
from server.models.base import TimestampMixin, S3Media, ConvertMixin


class User(TimestampMixin, ConvertMixin, Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    uid = Column(String(30), unique=True, nullable=False)
    password = Column(String(150), nullable=False)
    name = Column(String(30), nullable=False)
    mobile = Column(String(30), unique=True, nullable=False)
    email = Column(String(50), unique=True, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_staff = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    profiles = relationship("UserProfile", back_populates="user", lazy="selectin")
    sessions = relationship("UserSession", back_populates="user", lazy="selectin")


class UserProfile(TimestampMixin, ConvertMixin, Base):
    __tablename__ = "user_profiles"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    nickname = Column(String(30), nullable=False)
    status_message = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="profiles", lazy="joined")
    images = relationship(
        "UserProfileImage",
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin")
    rooms = relationship(
        "ChatRoomUserAssociation",
        back_populates="user_profile", cascade="all, delete", passive_deletes=True, lazy="selectin")
    chat_histories = relationship(
        "ChatHistory",
        back_populates="user_profile", cascade="all, delete", passive_deletes=True, lazy="selectin")
    chat_history_mapping = relationship(
        "ChatHistoryUserAssociation",
        back_populates="user_profile", cascade="all, delete", passive_deletes=True, lazy="selectin")


class UserRelationship(ConvertMixin, Base):
    __tablename__ = "user_relationships"

    id = Column(BigInteger, primary_key=True, index=True)
    my_profile_id = Column(BigInteger, ForeignKey("user_profiles.id"), nullable=False)
    other_profile_id = Column(BigInteger, ForeignKey("user_profiles.id"), nullable=False)
    type = Column(IntTypeEnum(enum_class=RelationshipType), default=RelationshipType.FRIEND, nullable=False)
    favorites = Column(Boolean, default=False, nullable=False)
    is_hidden = Column(Boolean, default=False, nullable=False)
    is_forbidden = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    my_profile = relationship("UserProfile", foreign_keys=[my_profile_id], lazy="joined")
    other_profile = relationship("UserProfile", foreign_keys=[other_profile_id], lazy="joined")


class UserProfileImage(S3Media):
    __tablename__ = "user_profile_images"

    id = Column(BigInteger, ForeignKey('s3_media.id'), primary_key=True)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    type = Column(IntTypeEnum(enum_class=ProfileImageType), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    profile = relationship("UserProfile", back_populates="images", lazy="joined")

    __mapper_args__ = {
        "polymorphic_load": "selectin",
        "polymorphic_identity": "user_profile_image"
    }


class UserSession(TimestampMixin, ConvertMixin, Base):
    __tablename__ = "user_sessions"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    session_id = Column(String(150), nullable=False)
    expiry_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="sessions", lazy="joined")
