from sqlalchemy import Column, BigInteger, String, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from server.db.databases import Base
from server.models.base import TimestampMixin


class ChatRoom(TimestampMixin, Base):
    __tablename__ = "chat_rooms"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(30), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    user_profiles = relationship(
        "ChatRoomUserAssociation", back_populates="room", cascade="all, delete", passive_deletes=True, lazy="selectin")
    histories = relationship("ChatHistory", back_populates="room", lazy="selectin")


class ChatRoomUserAssociation(TimestampMixin, Base):
    __tablename__ = "chat_room_user_association"

    room_id = Column(BigInteger, ForeignKey("chat_rooms.id", ondelete="CASCADE"), primary_key=True)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True)

    room = relationship("ChatRoom", back_populates="user_profiles", lazy="selectin")
    user_profile = relationship("UserProfile", back_populates="rooms", lazy="selectin")


class ChatHistory(TimestampMixin, Base):
    __tablename__ = "chat_histories"

    id = Column(BigInteger, primary_key=True, index=True)
    room_id = Column(BigInteger, ForeignKey("chat_rooms.id"), nullable=False)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id", ondelete="CASCADE"))
    contents = Column(Text, nullable=True)
    s3_media_id = Column(BigInteger, ForeignKey("s3_media.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    room = relationship("ChatRoom", back_populates="histories", lazy="selectin")
    user_profile = relationship("UserProfile", back_populates="histories", lazy="selectin")


class ChatHistoryUserAssociation(Base):
    __tablename__ = "chat_history_user_association"

    history_id = Column(BigInteger, ForeignKey("chat_histories.id", ondelete="CASCADE"), primary_key=True)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True)
    is_read = Column(Boolean, default=False, nullable=False)

    history = relationship("ChatHistory", back_populates="user_profiles", lazy="selectin")
    user_profile = relationship("UserProfile", back_populates="histories", lazy="selectin")
