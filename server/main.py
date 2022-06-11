from typing import List, Mapping

import uvicorn
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from sqlalchemy import create_engine
from starlette import status
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocket, WebSocketDisconnect

from server.core.responses import WebsocketJSONResponse
from server.core.utils.codes.websockets import CLIENT_DISCONNECT
from server.databases import DATABASE_URL, initialize_sql
from server.routers import user as user_routers

app = FastAPI(default_response_class=WebsocketJSONResponse)

engine = create_engine(DATABASE_URL)
initialize_sql(engine)

app.add_middleware(
    CORSMiddleware,
)

app.include_router(user_routers.router)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    err_data = jsonable_encoder({
        "response": 0,
        "error": exc.errors()
    })
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=err_data)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    err_data = {
        "response": 0,
        "error": exc.detail
    }
    headers = getattr(exc, "headers", None)
    if headers:
        return JSONResponse(err_data, status_code=exc.status_code, headers=headers)
    else:
        return JSONResponse(err_data, status_code=exc.status_code)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Mapping[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        connections_for_room = self.active_connections.get(room_id, [])
        connections_for_room.append(websocket)
        self.active_connections[room_id] = connections_for_room

    def disconnect(self, websocket: WebSocket, room_id: str):
        if websocket in self.active_connections[room_id]:
            self.active_connections[room_id].remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str, room_id: str):
        for connection in self.active_connections[room_id]:
            await connection.send_text(message)


manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/chat/{room_id}/{client_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, client_id: str):
    await manager.connect(websocket, room_id)
    # TODO : DB 에서 room_id & client_id 매핑 여부 확인 -> 매핑되어 있지 않을 시 브로드캐스트로 입장 메시지 송신
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Client #{client_id} says: {data}", room_id)
    except WebSocketDisconnect as e:
        # 반드시 웹소켓 연결 해제 후, 브로드캐스트 진행
        manager.disconnect(websocket, room_id)
        if e.code == CLIENT_DISCONNECT:
            await manager.broadcast(f"Client #{client_id} left the chat", room_id)


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
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
