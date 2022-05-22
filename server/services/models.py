from sqlalchemy import Column, BigInteger, String, DateTime, func, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from server.base.models import TimestampMixin
from server.databases import Base


class ChatRoom(TimestampMixin, Base):
    __tablename__ = "chat_rooms"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(30), nullable=False)

    user_mapping = relationship("ChatRoomUserMapping", back_populates="room")
    histories = relationship("ChatHistory", back_populates="room")


class ChatRoomUserMapping(TimestampMixin, Base):
    __tablename__ = "chat_room_user_mapping"

    id = Column(BigInteger, primary_key=True, index=True)
    room_id = Column(BigInteger, ForeignKey("chat_rooms.id"), nullable=False)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id"), nullable=False)
    name = Column(String(30), nullable=True)

    room = relationship("ChatRoom", back_populates="user_mapping")
    user_profile = relationship("base.UserProfile", back_populates="room_mapping")


class ChatHistory(TimestampMixin, Base):
    __tablename__ = "chat_histories"

    id = Column(BigInteger, primary_key=True, index=True)
    room_id = Column(BigInteger, ForeignKey("chat_rooms.id"), nullable=False)
    contents = Column(Text, nullable=True)
    s3_media_id = Column(BigInteger, ForeignKey("s3_media.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    room = relationship("ChatRoom", back_populates="histories")
