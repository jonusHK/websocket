from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, func, Text, ForeignKey
from sqlalchemy.orm import relationship

from server.databases import Base
from server.base.enums import RelationshipType, ProfileImageType
from server.base.utils import IntTypeEnum


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    uid = Column(String(30), nullable=False)
    password = Column(String(30), nullable=False)
    name = Column(String(30), nullable=False)
    mobile = Column(String(30), unique=True, nullable=False)
    email = Column(String(50), unique=True, nullable=True)
    last_login = Column(DateTime, nullable=True)
    is_staff = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)

    profiles = relationship("UserProfile", back_populates="user")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    nickname = Column(String(30), nullable=False)
    status_message = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="profiles")
    my_relationships = relationship("UserRelationship", back_populates="my_profile")
    other_relationships = relationship("UserRelationship", back_populates="other_profile")
    images = relationship("UserProfileImage", back_populates="profile")


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

    my_profile = relationship("UserProfile", back_populates="my_relationships")
    other_profile = relationship("UserProfile", back_populates="other_relationships")


class UserProfileImage(Base):
    __tablename__ = "user_profile_images"

    id = Column(BigInteger, primary_key=True, index=True)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id"), nullable=False)
    type = Column(IntTypeEnum(enum_class=ProfileImageType), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    profile = relationship("UserProfile", back_populates="images")
