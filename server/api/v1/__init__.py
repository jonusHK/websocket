from fastapi import APIRouter

from server.api.v1 import base, service, user

api_router = APIRouter()
api_router.include_router(base.router)
api_router.include_router(service.router, prefix="/services")
api_router.include_router(user.router, prefix="/users")
