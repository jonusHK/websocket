from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from server.config import settings

DATABASE_URL = "mysql+asyncmy://{username}:{password}@{host}:{port}/{db_name}".format(
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port,
    db_name=settings.db_name
)

engine = create_async_engine(DATABASE_URL, echo=True, future=True)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    # sessionmaker : 엔진의 연결 풀을 요청하고, 새로운 세션 객체와 연결하여, 새로운 세션 객체를 초기화하는 자동화 기능을 수행함
    async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
