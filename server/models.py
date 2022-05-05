from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, func, Text
from sqlalchemy.orm import relationship

from server.databases import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    uid = Column(String(30))
    password = Column(String(30))
    name = Column(String(30))
    mobile = Column(String(30), unique=True)
    email = Column(String(50), unique=True, nullable=True)
    last_login = Column(DateTime, nullable=True)
    is_staff = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), onupdate=func.now())

    profiles = relationship("UserProfile", back_populates="user")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(BigInteger, primary_key=True, index=True)
    nickname = Column(String(30))
    status_message = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="profiles")
