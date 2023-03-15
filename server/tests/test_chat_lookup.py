import logging
import uuid
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import selectinload, joinedload

from server.api.websocket.chat.proxy import ChatHandlerProxy
from server.core.enums import ChatType, ChatHistoryType
from server.core.externals.redis.schemas import RedisChatHistoryByRoomS, RedisChatHistoriesByRoomS
from server.crud.service import ChatRoomCRUD, ChatHistoryCRUD
from server.crud.user import UserProfileCRUD
from server.models import ChatRoom, UserProfile, ChatHistory
from server.schemas.chat import ChatReceiveFormS, ChatReceiveDataS
from server.tests.conftest import create_test_user_db, create_test_room_db

logger = logging.getLogger('test')


def generate_offset_limit(cnt: int, limit: int = 10):
    q, r = divmod(cnt, limit)

    if q == 0:
        yield 0, cnt

    for i in range(q):
        yield i * limit, limit

    if r:
        yield q * limit, r


async def test_메시지조회(db_setup, db_session, redis_handler):
    now = datetime.now().astimezone()

    total_cnt = 100
    cache_cnt = 70

    crud_room = ChatRoomCRUD(db_session)
    crud_user_profile = UserProfileCRUD(db_session)
    crud_chat_history = ChatHistoryCRUD(db_session)

    await create_test_user_db(db_session)
    await create_test_room_db(db_session)
    await db_session.commit()

    room: ChatRoom = await crud_room.get(conditions=(ChatRoom.id == 1,))
    user_profile: UserProfile = await crud_user_profile.get(conditions=(UserProfile.id == 1,))

    histories_bulk = [
        dict(
            redis_id=uuid.uuid4().hex,
            user_profile_id=user_profile.id,
            room_id=room.id,
            contents=f'message_{i}',
            type=ChatHistoryType.MESSAGE,
            created=now + timedelta(days=i),
        ) for i in range(total_cnt)
    ]
    await crud_chat_history.bulk_create(histories_bulk)

    histories_db: List[ChatHistory] = await crud_chat_history.list(
        order_by=(ChatHistory.created.desc(),),
        options=[
            selectinload(ChatHistory.user_profile_mapping),
            selectinload(ChatHistory.files),
            joinedload(ChatHistory.user_profile)
            .selectinload(UserProfile.images),
            joinedload(ChatHistory.user_profile)
            .selectinload(UserProfile.followers)
        ]
    )

    histories_redis = [
        RedisChatHistoryByRoomS(
            id=histories_db[i].id,
            redis_id=histories_db[i].redis_id,
            user_profile_id=histories_db[i].user_profile_id,
            contents=histories_db[i].contents,
            type=ChatHistoryType.MESSAGE.name.lower(),
            timestamp=histories_db[i].created.timestamp(),
            date=histories_db[i].created.date().isoformat(),
            is_active=histories_db[i].is_active
        ) for i in range(cache_cnt)
    ]
    await RedisChatHistoriesByRoomS.zadd(await redis_handler.redis, room.id, histories_redis)

    histories_origin = histories_redis + [
        await RedisChatHistoryByRoomS.from_model(m) for m in histories_db[cache_cnt:]
    ]

    histories: List[RedisChatHistoryByRoomS] = []
    for offset, limit in generate_offset_limit(total_cnt):
        receive = ChatReceiveFormS(
            type=ChatType.LOOKUP.name.lower(),
            data=ChatReceiveDataS(
                offset=offset,
                limit=limit
            )
        )
        histories.extend(
            await ChatHandlerProxy(receive, db_session).execute(
                redis_handler=redis_handler,
                user_profile_id=user_profile.id,
                room_id=room.id
            )
        )

    assert len(histories) == total_cnt

    for i, h in enumerate(histories):
        assert isinstance(h, RedisChatHistoryByRoomS)
        assert h.id == histories_origin[i].id
        assert h.user_profile_id == user_profile.id
        assert h.type == histories_origin[i].type
        assert h.date == histories_origin[i].date
        assert h.timestamp == histories_origin[i].timestamp
        assert h.contents == histories_origin[i].contents
