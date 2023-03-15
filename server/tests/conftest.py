import asyncio
from typing import AsyncGenerator

import pytest
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from server.api.common import AsyncRedisHandler, get_async_redis_handler
from server.core.enums import ChatRoomType
from server.core.utils import generate_random_string
from server.crud.service import ChatRoomCRUD
from server.crud.user import UserCRUD
from server.db.databases import Base, settings, get_async_session
from server.main import app
from server.models import UserProfile
from server.schemas.user import UserCreateS

base_url = 'http://localhost:8000/api/v1'
redis_endpoint = ['redis://localhost:6377']

DATABASE_URL = 'mysql+asyncmy://{username}:{password}@{host}:{port}/{db_name}'.format(
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port,
    db_name='test'
)

engine = create_async_engine(
    DATABASE_URL,
    echo=True, future=True,
    pool_recycle=3600,
    isolation_level='READ COMMITTED'
)
test_async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def override_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_async_session() as session:
        yield session


async def override_redis_handler() -> AsyncGenerator[AsyncRedisHandler, None]:
    async with AsyncRedisHandler(endpoint=redis_endpoint) as redis_handler:
        yield redis_handler


app.dependency_overrides[get_async_session] = override_async_session
app.dependency_overrides[get_async_redis_handler] = override_redis_handler


@pytest.fixture(scope='session')
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='function')
async def db_setup():
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
            yield
        finally:
            await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope='function')
async def db_session():
    async with test_async_session() as session:
        yield session


@pytest.fixture(scope='function')
async def redis_handler():
    async with AsyncRedisHandler(endpoint=redis_endpoint) as redis_handler:
        try:
            yield redis_handler
        finally:
            await redis_handler._flushall()


@pytest.fixture(scope='function')
async def client():
    async with AsyncClient(app=app, base_url=base_url) as client:
        yield client


async def create_test_user(
    session: AsyncSession,
    email='test@test.com', name='test', mobile='01011111111', password='test',
    is_superuser=False, is_staff=False, is_active=True
):
    crud_user = UserCRUD(session)

    user_s = UserCreateS(
        email=email, name=name, mobile=mobile, password=password,
        is_superuser=is_superuser, is_staff=is_staff, is_active=is_active
    )
    user = await crud_user.create(**jsonable_encoder(user_s))
    user.profiles.append(
        UserProfile(
            user=user,
            identity_id=generate_random_string(),
            nickname=user.name,
            is_default=True
        )
    )
    await session.commit()


async def create_test_room(session: AsyncSession, type_=ChatRoomType.PUBLIC, is_active=True, name=None):
    crud_room = ChatRoomCRUD(session)
    await crud_room.create(name=name, type=type_, is_active=is_active)
    await session.commit()
