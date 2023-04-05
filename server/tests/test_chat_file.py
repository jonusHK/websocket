import base64
import mimetypes
import os
import random
from typing import List

from server.api.websocket.chat.decorator import ChatHandlerDecorator
from server.core.enums import ChatType
from server.core.externals.redis.schemas import RedisChatHistoryByRoomS, \
    RedisChatHistoryFileS
from server.crud.service import ChatRoomUserAssociationCRUD, ChatRoomCRUD
from server.models import User, ChatRoom, UserProfile
from server.schemas.chat import ChatReceiveFormS, ChatReceiveDataS, ChatReceiveFileS
from server.tests.conftest import create_test_user_db, create_test_room_db


async def test_파일전송(db_setup, db_session, redis_handler, s3_client, s3_bucket):
    crud_room = ChatRoomCRUD(db_session)
    crud_room_user_mapping = ChatRoomUserAssociationCRUD(db_session)

    users = []
    for i in range(1, 11):
        mobile_last = ''.join([
            random.choice('0123456789') for _ in range(8)
        ])
        user: User = await create_test_user_db(
            db_session, email=f'test{i}@test.com', name=f'test{i}',
            mobile=f'010{mobile_last}', password='test'
        )
        users.append(user)

    room: ChatRoom = await create_test_room_db(db_session)
    user_profile: UserProfile = users[0].profiles[0]
    user_profiles_by_room: List[UserProfile] = [u.profiles[0] for u in users]

    await crud_room_user_mapping.bulk_create([
        dict(
            room_id=room.id,
            user_profile_id=p.id
        ) for p in user_profiles_by_room
    ])

    await db_session.commit()

    user_profiles_redis, _ = await redis_handler.sync_user_profiles_in_room(
        room.id, user_profile.id, crud_room_user_mapping, raise_exception=True
    )
    room_redis, _ = await redis_handler.sync_room(room.id, crud_room)

    with open('./static/images/potato.png', 'rb') as f:
        filename = os.path.basename(f.name)
        content_type, _ = mimetypes.guess_type(filename)

        receive = ChatReceiveFormS(
            type=ChatType.FILE.name.lower(),
            data=ChatReceiveDataS(
                files=[
                    ChatReceiveFileS(
                        content=base64.b64encode(f.read()),
                        content_type=content_type,
                        filename=filename,
                    )
                ]
            ))

    history: RedisChatHistoryByRoomS = await ChatHandlerDecorator(receive, db_session).execute(
        redis_handler=redis_handler,
        user_profile_id=user_profile.id,
        user_profiles_redis=user_profiles_redis,
        room_id=room.id,
        room_redis=room_redis
    )

    assert len(history.files) > 0
    assert isinstance(history.files[0], RedisChatHistoryFileS)
    assert history.files[0].content_type == content_type
    assert history.files[0].filename == filename
    assert history.is_active is True
