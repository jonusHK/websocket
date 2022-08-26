from typing import List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship

from server.models.base import TimestampMixin, S3Media, SQLModel


class ChatRoom(SQLModel, TimestampMixin, table=True):
    __tablename__ = "chat_rooms"

    id: int = Field(primary_key=True, index=True)
    name: str = Field(max_length=30)

    user_profile_associations: List["ChatRoomUserAssociation"] = Relationship(
        sa_relationship=relationship(
            "ChatRoomUserAssociation", back_populates="room", cascade="all, delete", passive_deletes=True))
    histories: List[Optional["ChatHistory"]] = Relationship(
        sa_relationship=relationship("ChatHistory", back_populates="room"))


class ChatRoomUserAssociation(SQLModel, TimestampMixin, table=True):
    __tablename__ = "chat_room_user_association"

    room_id: int = Field(foreign_key="chat_rooms.id", primary_key=True)
    user_profile_id = Field(foreign_key="user_profiles.id", primary_key=True)

    room: ChatRoom = Relationship(back_populates="user_profiles")
    user_profile: "UserProfile" = Relationship(back_populates="rooms")


class ChatHistory(SQLModel, TimestampMixin, table=True):
    __tablename__ = "chat_histories"

    id: int = Field(primary_key=True, index=True)
    room_id: int = Field(foreign_key="chat_rooms.id")
    contents: Optional[str] = Field(sa_column=sa.Column(sa.Text, nullable=True))
    s3_media_id: Optional[int] = Field(foreign_key="s3_media.id", nullable=True)
    is_active: bool = Field(default=False)

    room: ChatRoom = Relationship(back_populates="histories")
    s3_media: Optional[S3Media] = Relationship(back_populates="histories")
