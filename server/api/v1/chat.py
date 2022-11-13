import asyncio
import json
import logging
from datetime import datetime
from typing import List

from aioredis import Redis
from aioredis.client import PubSub
from fastapi import APIRouter, Depends, HTTPException, Cookie, Query, Request
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import HTMLResponse

from server.api import ExceptionHandlerRoute, templates
from server.core.authentications import cookie, RoleChecker
from server.core.enums import UserType, ChatType
from server.core.exceptions import ExceptionHandler
from server.core.externals.redis import AioRedis
from server.core.externals.redis.schemas import RedisChatRoomDetailS, RedisUserProfilesByRoomS, \
    RedisChatHistoriesByRoomS
from server.crud.service import ChatRoomUserAssociationCRUD, ChatRoomCRUD, ChatHistoryCRUD, ChatHistoryFileCRUD
from server.crud.user import UserProfileCRUD
from server.db.databases import get_async_session
from server.models import service as service_models
from server.models import user as user_models
from server.schemas import chat as chat_schemas

router = APIRouter(route_class=ExceptionHandlerRoute)

logger = logging.getLogger("chat")


async def get_cookie(
    websocket: WebSocket,
    session: str | None = Cookie(default=None),
    token: str | None = Query(default=None)
):
    if not session and not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return session or token


@router.get("", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/rooms/create", dependencies=[Depends(cookie), Depends(RoleChecker([UserType.USER]))])
async def chat_room_create(
    data: chat_schemas.ChatRoomCreate,
    session: AsyncSession = Depends(get_async_session),
    request_user: user_models.User = Depends(RoleChecker([UserType.USER]))
):
    """
    대화방 생성
    1) 1:1
    2) 1:N
    """
    crud_user_profile = UserProfileCRUD(session)
    crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)
    crud_room = ChatRoomCRUD(session)

    user_profile = await crud_user_profile.get(
        conditions=(
            user_models.UserProfile.id == data.user_profile_id,
            user_models.UserProfile.is_active == 1))
    if user_profile.user.id != request_user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized user profile.")
    target_profiles = await crud_user_profile.list(conditions=(
        user_models.UserProfile.id.in_(data.target_profile_ids),
        user_models.UserProfile.is_active == 1))
    if len(data.target_profile_ids) != len(target_profiles):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Not exists all for target profile ids.")

    # 유저와 대화방 매핑
    default_room_name = ", ".join([user_profile.nickname] + [profile.nickname for profile in target_profiles])
    room = await crud_room.create(name=default_room_name)
    await session.flush()
    current_profile_ids = set()
    add_profile_ids = set([data.user_profile_id] + data.target_profile_ids)
    profile_ids = add_profile_ids - current_profile_ids
    if not profile_ids:
        return []
    await crud_room_user_mapping.bulk_create([
        dict(room_id=room.id, user_profile_id=profile_id) for profile_id in profile_ids])
    await session.commit()
    await session.refresh(room)

    return profile_ids


# TODO session_id 사용하여 user_profile_id 추출
@router.websocket("/{user_profile_id}/{room_id}")
async def chat(
    websocket: WebSocket,
    user_profile_id: int,
    room_id: int,
    session: AsyncSession = Depends(get_async_session),
    # cookie: str = Depends(get_cookie)
):
    """
    대화 방 입장 및 실시간 채팅
    """
    def get_log_error(exc: Exception):
        return f"Chat Error - room_id: {room_id}, user_profile_id: {user_profile_id}, "\
               f"reason: {exc}"

    now = datetime.now().astimezone()
    redis = AioRedis().redis

    crud_room = ChatRoomCRUD(session)
    crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)
    crud_chat_history = ChatHistoryCRUD(session)

    try:
        # 방 존재 여부 확인
        try:
            while True:
                room = await RedisChatRoomDetailS.get(redis, room_id)
                if room:
                    break
                room = await crud_room.get(conditions=(
                    service_models.ChatRoom.id == room_id,
                    service_models.ChatRoom.is_active == 1))
                await RedisChatRoomDetailS.set(redis, room_id, RedisChatRoomDetailS.schema(
                    name=room.name,
                    is_active=room.is_active))
        except Exception as e:
            raise WebSocketDisconnect(
                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                reason=f"Not exist room. {e}")

        while True:
            user_profiles_by_room = await RedisUserProfilesByRoomS.lrange(redis, room_id)
            if user_profiles_by_room:
                break
            user_profiles_from_db = await crud_room_user_mapping.list(conditions=(
                service_models.ChatRoomUserAssociation.room_id == room_id,
                service_models.ChatRoomUserAssociation.user_profile_id == user_profile_id))
            if not user_profiles_from_db:
                break
            await RedisUserProfilesByRoomS.rpush(redis, room_id, *[
                RedisUserProfilesByRoomS.schema(
                    id=p.user_profile.id,
                    nickname=p.user_profile.nickname,
                    is_active=p.user_profile.is_active
                ) for p in user_profiles_from_db])

        # 방에 유저들이 접속되어 있는지 확인
        if not user_profiles_by_room:
            raise WebSocketDisconnect(
                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                reason="Not exist any user in the room.")

        # 방에 해당 유저가 접속되어 있는지 확인
        user_profile = next((p for p in user_profiles_by_room if p.id == user_profile_id), None)
        if not user_profile:
            raise WebSocketDisconnect(
                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                reason="Not exist the user in the room.")

    except Exception as e:
        code = e.code if isinstance(e, WebSocketDisconnect) else status.WS_1006_ABNORMAL_CLOSURE
        await websocket.close(code=code)
        raise WebSocketDisconnect(code=code, reason=ExceptionHandler(e).error)

    await websocket.accept()

    async def producer_handler(pub: Redis, ws: WebSocket):
        try:
            while True:
                data = await ws.receive_json()
                if not data:
                    continue
                try:
                    user_profiles_by_room = await RedisUserProfilesByRoomS.lrange(redis, room_id)
                    if not user_profiles_by_room:
                        raise WebSocketDisconnect(
                            code=status.WS_1001_GOING_AWAY, reason="Not exist any user in the room.")
                    if not next((p for p in user_profiles_by_room if p.id == user_profile_id), None):
                        raise WebSocketDisconnect(
                            code=status.WS_1001_GOING_AWAY, reason="Left the chat room.")

                    request_s = chat_schemas.ChatReceiveForm(**data)
                    # 업데이트 요청
                    if request_s.type == ChatType.UPDATE:
                        if not request_s.data.history_ids:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists chat history ids.")

                        chat_histories_by_room = await RedisChatHistoriesByRoomS.zrevrange(redis, room_id)
                        if not chat_histories_by_room:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists chat histories in the room.")

                        update_fields = (service_models.ChatHistory.is_active.name,)
                        # Redis 업데이트
                        redis_update_target: List[RedisChatHistoriesByRoomS.schema] = []
                        for history in chat_histories_by_room:
                            if history.id in request_s.data.history_ids:
                                for f in update_fields:
                                    if getattr(request_s.data, f) != getattr(history, f):
                                        redis_update_target.append(history)
                                        break
                        if redis_update_target:
                            for history in redis_update_target:
                                await RedisChatHistoriesByRoomS.zrem(redis, room_id, history)
                                for f in update_fields:
                                    setattr(history, f, getattr(request_s.data, f))
                                await RedisChatHistoriesByRoomS.zadd(redis, room_id, {history: history.timestamp})
                        # DB 업데이트
                        chat_histories = await crud_chat_history.list(conditions=(
                            service_models.ChatHistory.id.in_(request_s.data.history_ids)))
                        chat_history_ids = [h.id for h in chat_histories]
                        for v in update_fields:
                            if getattr(request_s.data, v) is not None:
                                await crud_chat_history.update(
                                    values={v: getattr(request_s.data, v)},
                                    conditions=(service_models.ChatHistory.id.in_(chat_history_ids)))
                        await session.commit()
                        response_s = chat_schemas.ChatSendForm(
                            type=request_s.type,
                            data=chat_schemas.ChatSendData(
                                history_ids=request_s.data.history_ids,
                                is_active=request_s.data.is_active))
                    # 메시지 요청
                    elif request_s.type == ChatType.MESSAGE:
                        # DB 저장
                        chat_history = await crud_chat_history.create(
                            room_id=room_id,
                            user_profile_id=user_profile_id,
                            contents=request_s.data.text)
                        await session.commit()
                        await session.refresh(chat_history)
                        # Redis 저장
                        history_s = RedisChatHistoriesByRoomS.schema(
                            id=chat_history.id,
                            user_profile_id=chat_history.user_profile_id,
                            contents=chat_history.contents,
                            read_user_ids=[user_profile_id],
                            timestamp=now.timestamp(),
                            is_active=True)
                        await RedisChatHistoriesByRoomS.zadd(redis, room_id, {history_s: history_s.timestamp})
                        response_s = chat_schemas.ChatSendForm(
                            type=request_s.type,
                            data=chat_schemas.ChatSendData(
                                user_profile_id=user_profile_id,
                                nickname=user_profile.nickname,
                                timestamp=now.timestamp(),
                                text=request_s.data.text,
                                is_active=request_s.data.is_active))
                    # 파일 요청
                    elif request_s.type == ChatType.FILE:
                        await crud_chat_history.bulk_create(values=[
                            dict(
                                room_id=room_id,
                                user_profile_id=user_profile_id
                            ) for _id in request_s.data.file_ids])
                        # TODO bulk_create 이후, ids 받아오는 방법 있을 시 리팩토링
                        chat_histories = await crud_chat_history.list(conditions=(
                            service_models.ChatHistory.room_id == room_id,
                            service_models.ChatHistory.user_profile_id == user_profile_id))
                        crud_chat_history_file = ChatHistoryFileCRUD(session)
                        await crud_chat_history_file.bulk_create(values=[
                            dict(
                                chat_history_id=h.id,
                                order=i+1
                            ) for i, h in enumerate(chat_histories)])
                        # TODO Redis 생성 및 response_s 생성
                        response_s = chat_schemas.ChatSendForm(
                            type=request_s.type,
                            data=chat_schemas.ChatSendData(
                                user_profile_id=user_profile_id,
                                nickname=user_profile.nickname,
                                timestamp=request_s.data.timestamp,
                                files=[],  # TODO
                                is_active=request_s.data.is_active))
                    # 대화 내용 조회
                    elif request_s.type == ChatType.LOOKUP:
                        if not request_s.data.offset or not request_s.data.limit:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists offset or limit for page.")
                        # TODO histories에 files 및 read_user_ids(user_profile_id 업데이트) 처리하여 전달
                        # Redis 에서 대화 내용 조회
                        chat_histories_from_redis = await RedisChatHistoriesByRoomS.zrevrange(
                            redis,
                            room_id,
                            start=request_s.data.offset,
                            end=request_s.data.offset + request_s.data.limit - 1)
                        # Redis 에 데이터 없는 경우 DB 에서 조회
                        lack_cnt = request_s.data.limit - len(chat_histories_from_redis)
                        if lack_cnt > 0:
                            if chat_histories_from_redis:
                                next_offset = request_s.data.offset + len(chat_histories_from_redis) + 1
                            else:
                                next_offset = request_s.data.offset
                            chat_histories_from_db = await crud_chat_history.list(
                                offset=next_offset,
                                limit=lack_cnt,
                                order_by=(getattr(service_models.ChatHistory, request_s.data.order_by).desc(),))
                            add_chat_histories = [
                                RedisChatHistoriesByRoomS.schema(
                                    id=h.id,
                                    user_profile_id=h.user_profile_id,
                                    contents=h.contents,
                                    read_user_ids=[user_profile_id],  # TODO DB 수정
                                    timestamp=h.created,
                                    is_active=h.is_active) for h in chat_histories_from_db
                            ] if chat_histories_from_db else []
                        else:
                            add_chat_histories = []

                        chat_histories = chat_histories_from_redis + add_chat_histories
                        response_s = chat_schemas.ChatSendForm(
                            type=ChatType.LOOKUP,
                            data=chat_schemas.ChatSendData(
                                histories=chat_histories,
                                timestamp=request_s.data.timestamp))
                    # 유저 초대
                    else:
                        current_profile_ids = {
                            p.id for p in user_profiles_by_room} if user_profiles_by_room else {user_profile_id}
                        target_user_profile_ids = request_s.data.target_user_profile_ids
                        if not target_user_profile_ids:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists user profile ids for invite")
                        add_profile_ids = set(request_s.data.target_user_profile_ids)
                        profile_ids = add_profile_ids - current_profile_ids
                        if not profile_ids:
                            continue
                        profiles = [p for p in user_profiles_by_room if p.id in profile_ids]
                        # Redis 업데이트
                        await RedisUserProfilesByRoomS.rpush(redis, room_id, *profiles)
                        # DB 업데이트
                        await crud_room_user_mapping.bulk_create([
                            dict(
                                room_id=room_id, user_profile_id=profile_id
                            ) for profile_id in profile_ids])
                        await session.commit()

                        # 대화방 초대 메시지 전송
                        user_profiles_by_room = await RedisUserProfilesByRoomS.lrange(redis, room_id)
                        new_user_profiles = [p for p in user_profiles_by_room if p.id in profile_ids]
                        if len(new_user_profiles) > 1:
                            target_msg = '님과 '.join([p.nickname for p in new_user_profiles])
                        else:
                            target_msg = new_user_profiles[0].nickname
                        response_s = chat_schemas.ChatSendForm(
                            type=ChatType.MESSAGE,
                            data=chat_schemas.ChatSendData(
                                text=f"{user_profile.nickname}님이 {target_msg}님을 초대했습니다.",
                                timestamp=now.timestamp()))
                    await pub.publish(f"chat:{room_id}", response_s.json())
                except WebSocketDisconnect as exc:
                    raise exc
                except Exception as exc:
                    logger.error(get_log_error(exc))
        except WebSocketDisconnect as e:
            logger.error(get_log_error(e))
            # TODO Redis 업데이트
            # DB 업데이트
            delete_conditions = (
                service_models.ChatRoomUserAssociation.room_id == room_id,
                service_models.ChatRoomUserAssociation.user_profile_id == user_profile_id)
            try:
                await crud_room_user_mapping.get(conditions=delete_conditions)
            except Exception:
                pass
            else:
                # 유저와 대화방 연결 해제
                await crud_room_user_mapping.delete(conditions=delete_conditions)
                await session.commit()
                # 유저 연결 해제 메시지 전송
                response_s = chat_schemas.ChatSendForm(
                    type=ChatType.MESSAGE,
                    data=chat_schemas.ChatSendData(
                        text=f"{user_profile.nickname}님이 나갔습니다.",
                        timestamp=now.timestamp()))
                await pub.publish(f"chat:{room_id}", response_s.json())
            raise e

    async def consumer_handler(psub: PubSub, ws: WebSocket):
        try:
            async with psub as p:
                await p.subscribe(f"chat:{room_id}")
                try:
                    while True:
                        message = await p.get_message(ignore_subscribe_messages=True)
                        if message:
                            await ws.send_json(json.loads(message.get('data')))
                except asyncio.CancelledError as e:
                    await p.unsubscribe()
                    raise e
                except Exception as e:
                    logger.error(get_log_error(e))
        except asyncio.CancelledError:
            await psub.close()

    redis = AioRedis().redis
    pubsub = redis.pubsub()

    producer_task = producer_handler(pub=redis, ws=websocket)
    consumer_task = consumer_handler(psub=pubsub, ws=websocket)
    done, pending = await asyncio.wait(
        [producer_task, consumer_task], return_when=asyncio.FIRST_COMPLETED)
    logger.info(f"Done task: {done}")
    for task in pending:
        logger.info(f"Canceling task: {task}")
        task.cancel()
