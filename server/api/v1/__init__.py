from fastapi import APIRouter

from server.api.v1 import base, service, user, chat, redis

api_router = APIRouter()
api_router.include_router(base.router)
api_router.include_router(service.router, prefix="/services")
api_router.include_router(user.router, prefix="/users")
api_router.include_router(chat.router, prefix="/chats")
api_router.include_router(redis.router, prefix="/redis")
