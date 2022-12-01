from sqlalchemy import Column, BigInteger, String, ForeignKey, Text, Boolean, Integer
from sqlalchemy.orm import relationship

from server.db.databases import Base
from server.models.base import TimestampMixin, S3Media


class ChatRoom(TimestampMixin, Base):
    __tablename__ = "chat_rooms"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(30), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    user_profiles = relationship(
        "ChatRoomUserAssociation", back_populates="room", cascade="all, delete", passive_deletes=True, lazy="selectin")
    chat_histories = relationship("ChatHistory", back_populates="room", lazy="selectin")


class ChatRoomUserAssociation(TimestampMixin, Base):
    __tablename__ = "chat_room_user_association"

    room_id = Column(BigInteger, ForeignKey("chat_rooms.id", ondelete="CASCADE"), primary_key=True)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True)

    room = relationship("ChatRoom", back_populates="user_profiles", lazy="joined")
    user_profile = relationship("UserProfile", back_populates="rooms", lazy="joined")


class ChatHistory(TimestampMixin, Base):
    __tablename__ = "chat_histories"

    id = Column(BigInteger, primary_key=True, index=True)
    room_id = Column(BigInteger, ForeignKey("chat_rooms.id"), nullable=False)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id", ondelete="CASCADE"))
    contents = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    room = relationship("ChatRoom", back_populates="chat_histories", lazy="joined")
    user_profile = relationship("UserProfile", back_populates="chat_histories", lazy="joined")
    files = relationship("ChatHistoryFile", back_populates="chat_history", lazy="selectin")
    user_profile_mapping = relationship(
        "ChatHistoryUserAssociation",
        back_populates="history", cascade="all, delete", passive_deletes=True, lazy="selectin")


class ChatHistoryFile(S3Media):
    __tablename__ = "chat_history_files"

    id = Column(BigInteger, ForeignKey('s3_media.id'), primary_key=True)
    chat_history_id = Column(BigInteger, ForeignKey("chat_histories.id", ondelete="CASCADE"), nullable=False)
    order = Column(Integer, default=1, unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    chat_history = relationship("ChatHistory", back_populates="files")

    __mapper_args__ = {
        "polymorphic_load": "selectin",
        "polymorphic_identity": "chat_history"
    }


# 채팅 내역을 읽을 유저들 간의 관계
class ChatHistoryUserAssociation(Base):
    __tablename__ = "chat_history_user_association"

    history_id = Column(BigInteger, ForeignKey("chat_histories.id", ondelete="CASCADE"), primary_key=True)
    user_profile_id = Column(BigInteger, ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True)
    is_read = Column(Boolean, default=True, nullable=False)

    history = relationship("ChatHistory", back_populates="user_profile_mapping", lazy="joined")
    user_profile = relationship("UserProfile", back_populates="chat_history_mapping", lazy="joined")
