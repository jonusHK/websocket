from functools import lru_cache
from typing import List, Mapping

import uvicorn
from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocket, WebSocketDisconnect

from server import config
from server.databases import SessionLocal, engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
)


@lru_cache()
def get_settings():
    return config.Settings()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


class ConnectionManager:
    def __init__(self):
        self.active_connections: Mapping[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        connections_for_room = self.active_connections.get(room_id, [])
        connections_for_room.append(websocket)
        self.active_connections[room_id] = connections_for_room

    def disconnect(self, websocket: WebSocket, room_id: str):
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
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.broadcast(f"Client #{client_id} says: {data}", room_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
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
