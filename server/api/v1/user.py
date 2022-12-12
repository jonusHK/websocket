import asyncio
import json
import logging
from datetime import datetime
from typing import List
from uuid import uuid4, UUID

from aioredis import Redis
from aioredis.client import PubSub
from fastapi import APIRouter, Depends, HTTPException, Response, status, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.websockets import WebSocket, WebSocketDisconnect

from server.api import ExceptionHandlerRoute
from server.api.common import AuthValidator, RedisHandler
from server.core.authentications import SessionData, backend, cookie, verifier, RoleChecker
from server.core.enums import UserType, ProfileImageType
from server.core.exceptions import ExceptionHandler
from server.core.externals.redis import AioRedis
from server.core.externals.redis.schemas import RedisFollowingsByUserProfileS, RedisFollowingByUserProfileS
from server.core.utils import verify_password
from server.crud.user import UserCRUD, UserProfileCRUD
from server.db.databases import get_async_session, settings
from server.models import UserSession, UserProfileImage, User, UserProfile, UserRelationship
from server.schemas.user import UserS, UserSessionS, UserCreateS, UserProfileImageS, UserProfileImageUploadS

router = APIRouter(route_class=ExceptionHandlerRoute)

logger = logging.getLogger("websocket")


@router.post(
    "/signup",
    response_model=UserS,
    response_model_include={"id", "uid"},
    status_code=status.HTTP_201_CREATED
)
async def signup(user_s: UserCreateS, session: AsyncSession = Depends(get_async_session)):
    user_crud = UserCRUD(session)

    try:
        await user_crud.get(conditions=(User.uid == user_s.uid,))
    except HTTPException:
        pass
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Already signed up.')
    user = await user_crud.create(**jsonable_encoder(user_s))
    user.profiles.append(UserProfile(user=user, nickname=user.name, is_default=True))
    await session.commit()
    await session.refresh(user)

    return UserS.from_orm(user)


@router.post(
    "/login",
    response_model=UserS,
    response_model_include={"id"}
)
async def login(data: SessionData, response: Response, session: AsyncSession = Depends(get_async_session)):
    session_id = uuid4()
    crud = UserCRUD(session)

    user = await crud.get(conditions=(User.uid == data.uid,))
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid uid.")
    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password.")

    await backend.create(session_id, data, session)
    cookie.attach_to_response(response, session_id)  # 저장 되는 쿠키 값: str(cookie.signer.dumps(session_id.hex))
    await crud.update(
        conditions=(User.id == user.id,),
        values=dict(last_login=datetime.now().astimezone()))
    await session.commit()
    return UserS.from_orm(user)


@router.get("/whoami", dependencies=[Depends(cookie)])
async def whoami(user_session: UserSession = Depends(verifier)):
    return UserSessionS.from_orm(user_session)


@router.get("/permission", dependencies=[Depends(cookie), Depends(RoleChecker([UserType.USER]))])
async def permission_test():
    return {"detail": "ok"}


@router.post("/logout")
async def logout(
        response: Response, session_id: UUID = Depends(cookie), session: AsyncSession = Depends(get_async_session)):
    await backend.delete(session_id, session)
    cookie.delete_from_response(response)
    await session.commit()
    return


# 유저 프로필, 배경 이미지 업로드
@router.post("/profile/image/upload", dependencies=[Depends(cookie)])
async def user_profile_image_upload(
    file: UploadFile,
    upload_s: UserProfileImageUploadS = Depends(),
    user_session: UserSession = Depends(verifier),
    session=Depends(get_async_session)
):
    if upload_s.user_profile_id not in [p.id for p in user_session.user.profiles]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    objects: List[UserProfileImage] = []
    async for o in UserProfileImage.files_to_models(
        session,
        [file],
        root='user_profile/',
        user_profile_id=upload_s.user_profile_id,
        type=ProfileImageType.get_by_name(upload_s.image_type),
        is_default=upload_s.is_default,
        bucket_name=settings.aws_storage_bucket_name
    ):
        objects.append(o)

    try:
        session.add_all(objects)
        await session.commit()
        for o in objects:
            await session.refresh(o)

        if len(objects) == 1:
            await objects[0].upload()
        else:
            await UserProfileImage.asynchronous_upload(*objects)
    finally:
        for o in objects:
            o.close()

    return [UserProfileImageS.from_orm(o) for o in objects]


@router.websocket('/followers')
async def followers(
    websocket: WebSocket,
    user_profile_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """
    친구 목록 조회
    """
    def get_log_error(exc: Exception):
        return f"Followings Error - user_profile_id: {user_profile_id}, " \
               f"reason: {ExceptionHandler(exc).error}"

    user: User = await AuthValidator(session).get_user_by_websocket(websocket)
    user_profile: UserProfile = next((p for p in user.profiles if p.id == user_profile_id and p.is_active), None)
    if not user_profile:
        raise WebSocketDisconnect(code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA, reason='Unauthorized user.')

    redis: Redis = AioRedis().redis
    redis_handler = RedisHandler(redis)
    crud_user_profile = UserProfileCRUD(session)

    await websocket.accept()

    async def producer_handler(pub: Redis, ws: WebSocket):
        try:
            while True:
                # TODO refactoring
                while True:
                    followings: List[RedisFollowingByUserProfileS] = await RedisFollowingsByUserProfileS.zrange(redis, user_profile_id)
                    if followings:
                        break
                    if not followings:
                        user_profile: UserProfile = await crud_user_profile.get(
                            conditions=(UserProfile.id == user_profile_id,),
                            options=[
                                selectinload(UserProfile.followers).
                                joinedload(UserRelationship.other_profile).
                                selectinload(UserProfile.images)
                            ])
                        await RedisFollowingsByUserProfileS.zadd(redis, user_profile_id, [
                            RedisFollowingsByUserProfileS.schema(
                                id=f.other_profile_id,
                                nickname=f.other_profile.nickname,
                                files=await redis_handler.generate_presigned_files(
                                    UserProfileImage, [i for i in f.other_profile.images if i.is_default])
                            ) for f in user_profile.followings
                        ])
                await pub.publish(f'pubsub:user:{user_profile_id}:following', json.dumps(jsonable_encoder(followings)))
        except WebSocketDisconnect as e:
            logger.exception(e)
            raise e
        except Exception as e:
            logger.exception(e)

    async def consumer_handler(psub: PubSub, ws: WebSocket):
        try:
            async with psub as p:
                await p.subscribe(f"pubsub:user:{user_profile_id}:chat_room")
                try:
                    while True:
                        message: dict = await p.get_message(ignore_subscribe_messages=True)
                        if message:
                            await ws.send_json(json.loads(message.get('data')))
                except asyncio.CancelledError as exc:
                    await p.unsubscribe()
                    raise exc
                except Exception as exc:
                    logger.error(get_log_error(exc))
        except asyncio.CancelledError:
            await psub.close()

    await redis_handler.handle_pubsub(websocket, producer_handler, consumer_handler, logger)
