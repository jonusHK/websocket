import logging
from typing import List

import uvicorn
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from server.api.common import get_async_redis_handler
from server.api.v1 import api_router
from server.core.exceptions import ClassifiableException
from server.core.externals.redis.schemas import RedisInfoByRoomS
from server.core.responses import WebsocketJSONResponse
from server.db.databases import settings, engine, Base

logging.config.fileConfig("logging.conf", disable_existing_loggers=False)

# app = FastAPI(root_path="/api/v1", default_response_class=WebsocketJSONResponse)
app = FastAPI(default_response_class=WebsocketJSONResponse)

if settings.backend_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(map(str, settings.backend_cors_origins)),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.api_v1_prefix)

app.mount("/static", StaticFiles(directory="static"), name="static")


async def init_chat_room_redis():
    redis_handler_gen = anext(get_async_redis_handler())
    redis_handler = await redis_handler_gen
    room_keys: List[str] = (await RedisInfoByRoomS.scan(await redis_handler.redis))[1]
    if room_keys:
        await RedisInfoByRoomS.delete(await redis_handler.redis, *room_keys, raw_key=True)


@app.on_event("startup")
async def on_startup():
    # create db tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    log_level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(level=log_level)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    await init_chat_room_redis()


@app.on_event("shutdown")
async def shutdown_event():
    await init_chat_room_redis()


@app.exception_handler(ClassifiableException)
async def exception_handler(request: Request, exc: ClassifiableException):
    err_response = exc.code.retrieve()
    err_response.update({
        "data": exc.detail
    })
    kwargs = {
        "status_code": exc.status_code,
        "content": jsonable_encoder(err_response)
    }
    return JSONResponse(**kwargs)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
