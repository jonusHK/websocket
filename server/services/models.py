from sqlalchemy import Column, BigInteger, String, DateTime, func, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from server.databases import Base


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(30), nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)

    user_mapping = relationship("ChatRoomUserMapping", back_populates="room")


class ChatRoomUserMapping(Base):
    __tablename__ = "chat_room_user_mapping"

    id = Column(BigInteger, primary_key=True, index=True)
    room_id = Column(BigInteger, ForeignKey("chat_rooms.id"), nullable=False)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id"), nullable=False)
    name = Column(String(30), nullable=True)
    created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)

    room = relationship("ChatRoom", back_populates="user_mapping")
    user_profile = relationship("base.UserProfile", back_populates="room_mapping")
    histories = relationship("ChatHistory", back_populates="room_user_mapping")


class ChatHistory(Base):
    __tablename__ = "chat_histories"

    id = Column(BigInteger, primary_key=True, index=True)
    room_user_mapping_id = Column(BigInteger, ForeignKey("chat_room_user_mapping.id"), nullable=False)
    contents = Column(Text, nullable=True)
    s3_media_id = Column(BigInteger, ForeignKey("s3_media.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)

    room_user_mapping = relationship("ChatRoomUserMapping", back_populates="histories")
