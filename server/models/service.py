from sqlalchemy import Column, BigInteger, String, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from server.databases import Base
from server.models.base import TimestampMixin


class ChatRoom(TimestampMixin, Base):
    __tablename__ = "chat_rooms"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(30), nullable=False)

    user_profiles = relationship("ChatRoomUserAssociation", back_populates="room")
    histories = relationship("ChatHistory", back_populates="room")


class ChatRoomUserAssociation(TimestampMixin, Base):
    __tablename__ = "chat_room_user_association"

    room_id = Column(BigInteger, ForeignKey("chat_rooms.id"), primary_key=True)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id"), primary_key=True)

    room = relationship("ChatRoom", back_populates="user_profiles")
    user_profile = relationship("UserProfile", back_populates="rooms")


class ChatHistory(TimestampMixin, Base):
    __tablename__ = "chat_histories"

    id = Column(BigInteger, primary_key=True, index=True)
    room_id = Column(BigInteger, ForeignKey("chat_rooms.id"), nullable=False)
    contents = Column(Text, nullable=True)
    s3_media_id = Column(BigInteger, ForeignKey("s3_media.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    room = relationship("ChatRoom", back_populates="histories")
