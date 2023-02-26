from typing import List

from fastapi import APIRouter

from server.api import ExceptionHandlerRoute
from server.core.externals.redis import AioRedis
from server.core.externals.redis.schemas import (
    RedisUserProfilesByRoomS, RedisChatRoomsByUserProfileS, RedisChatHistoriesByRoomS,
    RedisFollowingsByUserProfileS, RedisInfoByRoomS
)

router = APIRouter(route_class=ExceptionHandlerRoute)


@router.get('/rooms')
async def chat_rooms():
    redis = AioRedis().redis
    room_keys: List[str] = (await RedisInfoByRoomS.scan(redis))[1]
    if not room_keys:
        return []
    return [await RedisInfoByRoomS.hgetall(redis, key, raw_key=True) for key in room_keys]


@router.get('/rooms/{room_id}')
async def chat_room(room_id: int):
    redis = AioRedis().redis
    return await RedisInfoByRoomS.hgetall(redis, room_id)


@router.get('/rooms/user_profile/{user_profile_id}')
async def chat_rooms_by_user_profile(user_profile_id: int):
    redis = AioRedis().redis
    return await RedisChatRoomsByUserProfileS.zrange(redis, user_profile_id)


@router.get('/user_profiles/{room_id}/{user_profile_id}')
async def user_profiles_by_room(room_id: int, user_profile_id: int):
    redis = AioRedis().redis
    return await RedisUserProfilesByRoomS.smembers(redis, (room_id, user_profile_id))


@router.get('/chats/{room_id}')
async def chat_histories_by_room(room_id: int):
    redis = AioRedis().redis
    return await RedisChatHistoriesByRoomS.zrange(redis, room_id)


@router.get('/followings/{user_profile_id}')
async def followings_by_user_profile(user_profile_id: int):
    redis = AioRedis().redis
    return await RedisFollowingsByUserProfileS.smembers(redis, user_profile_id)
