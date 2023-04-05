from typing import List

from sqlalchemy.orm import selectinload

from server.api.websocket.chat.decorator import ChatHandlerDecorator
from server.core.enums import ChatType
from server.core.externals.redis.schemas import RedisChatHistoriesByRoomS, RedisChatHistoryByRoomS
from server.crud.service import ChatHistoryCRUD
from server.models import ChatRoom, User, ChatHistory, UserProfile
from server.schemas.chat import ChatReceiveFormS, ChatReceiveDataS
from server.tests.conftest import create_test_user_db, create_test_room_db, create_test_chat_message_db


async def test_메시지업데이트(db_setup, db_session, redis_handler):
    total_cnt = 100
    cache_cnt = 70

    crud_chat_history = ChatHistoryCRUD(db_session)

    user: User = await create_test_user_db(db_session)
    room: ChatRoom = await create_test_room_db(db_session)
    user_profile: UserProfile = user.profiles[0]
    await create_test_chat_message_db(db_session, room.id, user_profile.id, cnt=total_cnt)
    await db_session.commit()

    histories: List[ChatHistory] = await crud_chat_history.list(
        options=[
            selectinload(ChatHistory.user_profile_mapping),
            selectinload(ChatHistory.files)
        ]
    )

    sync_histories: List[ChatHistory] = histories[total_cnt-cache_cnt:]

    await RedisChatHistoriesByRoomS.zadd(await redis_handler.redis, room.id, [
        await RedisChatHistoryByRoomS.from_model(h) for h in sync_histories
    ])

    receive = ChatReceiveFormS(
        type=ChatType.PATCH.name.lower(),
        data=ChatReceiveDataS(
            history_redis_ids=[h.redis_id for h in histories],
            is_active=False
        )
    )

    patch_histories: List[RedisChatHistoryByRoomS] = await ChatHandlerDecorator(receive, db_session).execute(
        redis_handler=redis_handler,
        user_profile_id=user_profile.id,
        room_id=room.id,
    )

    assert len(patch_histories) == total_cnt
    for h in patch_histories:
        assert h.is_active is receive.data.is_active
