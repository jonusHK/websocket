from typing import List

from fastapi import APIRouter

from server.api import ExceptionHandlerRoute
from server.api.common import RedisHandler
from server.core.externals.redis.schemas import (
    RedisUserProfilesByRoomS, RedisChatRoomsByUserProfileS, RedisChatHistoriesByRoomS,
    RedisFollowingsByUserProfileS, RedisInfoByRoomS
)

router = APIRouter(route_class=ExceptionHandlerRoute)


@router.get('/rooms')
async def chat_rooms():
    redis_hdr = RedisHandler()
    try:
        room_keys: List[str] = (await RedisInfoByRoomS.scan(await redis_hdr.redis))[1]
        if not room_keys:
            return []
        return [await RedisInfoByRoomS.hgetall(await redis_hdr.redis, key, raw_key=True) for key in room_keys]
    finally:
        await redis_hdr.close()


@router.get('/rooms/{room_id}')
async def chat_room(room_id: int):
    redis_hdr = RedisHandler()
    try:
        return await RedisInfoByRoomS.hgetall(await redis_hdr.redis, room_id)
    finally:
        await redis_hdr.close()


@router.get('/rooms/user_profile/{user_profile_id}')
async def chat_rooms_by_user_profile(user_profile_id: int):
    redis_hdr = RedisHandler()
    try:
        return await RedisChatRoomsByUserProfileS.zrange(await redis_hdr.redis, user_profile_id)
    finally:
        await redis_hdr.close()


@router.get('/user_profiles/{room_id}/{user_profile_id}')
async def user_profiles_by_room(room_id: int, user_profile_id: int):
    redis_hdr = RedisHandler()
    try:
        return await RedisUserProfilesByRoomS.smembers(await redis_hdr.redis, (room_id, user_profile_id))
    finally:
        await redis_hdr.close()


@router.get('/chats/{room_id}')
async def chat_histories_by_room(room_id: int):
    redis_hdr = RedisHandler()
    try:
        return await RedisChatHistoriesByRoomS.zrange(await redis_hdr.redis, room_id)
    finally:
        await redis_hdr.close()


@router.get('/followings/{user_profile_id}')
async def followings_by_user_profile(user_profile_id: int):
    redis_hdr = RedisHandler()
    try:
        return await RedisFollowingsByUserProfileS.smembers(await redis_hdr.redis, user_profile_id)
    finally:
        await redis_hdr.close()
