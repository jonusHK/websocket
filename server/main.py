import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from server.api.v1 import api_router
from server.core.exceptions import ClassifiableException
from server.core.responses import WebsocketJSONResponse
from server.db.databases import settings, engine, Base

logging.config.fileConfig("logging.conf", disable_existing_loggers=False)

# app = FastAPI(root_path="/api/v1", default_response_class=WebsocketJSONResponse)
app = FastAPI(default_response_class=WebsocketJSONResponse)

if settings.backend_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.backend_cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.api_v1_prefix)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def on_startup():
    # create db tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


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


# @app.websocket_route("/chat")
# class WebSocketChat(WebSocketEndpoint):
#     async def on_connect(self, websocket):
#         await manager.connect(websocket)
#
#     async def on_receive(self, websocket: WebSocket, data) -> None:
#         await manager.send_personal_message(f"You wrote: {data}", websocket)
#
#     async def on_disconnect(self, websocket, close_code):
#         await websocket.close(code=status.WS_1001_GOING_AWAY)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
