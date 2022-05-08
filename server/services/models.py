from sqlalchemy import Column, BigInteger, String, DateTime, func

from server.databases import Base


class ChatRoom(Base):
    __tablename__ = "chat_room"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(30), nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)
