from typing import List, Optional

from fastapi import APIRouter, Depends

from server.api import ExceptionHandlerRoute
from server.api.common import AsyncRedisHandler, get_async_redis_handler
from server.core.externals.redis.schemas import (
    RedisUserProfilesByRoomS, RedisChatRoomsByUserProfileS, RedisChatHistoriesByRoomS,
    RedisFollowingsByUserProfileS, RedisInfoByRoomS
)

router = APIRouter(route_class=ExceptionHandlerRoute)


@router.get('/rooms')
async def chat_rooms(redis_handler: AsyncRedisHandler = Depends(get_async_redis_handler)):
    room_keys: List[str] = (await RedisInfoByRoomS.scan(await redis_handler.redis))[1]
    if not room_keys:
        return []
    return [await RedisInfoByRoomS.hgetall(await redis_handler.redis, key, raw_key=True) for key in room_keys]


@router.get('/rooms/{room_id}')
async def chat_room(
    room_id: int,
    redis_handler: AsyncRedisHandler = Depends(get_async_redis_handler)
):
    return await RedisInfoByRoomS.hgetall(await redis_handler.redis, room_id)


@router.get('/rooms/user_profile/{user_profile_id}')
async def chat_rooms_by_user_profile(
    user_profile_id: int,
    redis_handler: AsyncRedisHandler = Depends(get_async_redis_handler)
):
    return await RedisChatRoomsByUserProfileS.zrange(await redis_handler.redis, user_profile_id)


@router.get('/user_profiles/{room_id}/{user_profile_id}')
async def user_profiles_by_room(
    room_id: int,
    user_profile_id: int,
    redis_handler: AsyncRedisHandler = Depends(get_async_redis_handler)
):
    return await RedisUserProfilesByRoomS.smembers(await redis_handler.redis, (room_id, user_profile_id))


@router.get('/chats/{room_id}')
async def chat_histories_by_room(
    room_id: int,
    redis_handler: AsyncRedisHandler = Depends(get_async_redis_handler)
):
    return await RedisChatHistoriesByRoomS.zrange(await redis_handler.redis, room_id)


@router.get('/followings/{user_profile_id}')
async def followings_by_user_profile(
    user_profile_id: int,
    redis_handler: AsyncRedisHandler = Depends(get_async_redis_handler)
):
    return await RedisFollowingsByUserProfileS.smembers(await redis_handler.redis, user_profile_id)


@router.delete('/followings/{user_profile_id}')
async def delete_followings_by_user_profile(
    user_profile_id: int,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    redis_handler: AsyncRedisHandler = Depends(get_async_redis_handler)
):
    followings = await RedisFollowingsByUserProfileS.smembers(await redis_handler.redis, user_profile_id)
    targets = [f for f in followings if f.id == target_id or f.nickname == target_name]
    return await RedisFollowingsByUserProfileS.srem(await redis_handler.redis, user_profile_id, *targets)
