from typing import Dict, List

from fastapi import Request, APIRouter
from starlette.responses import HTMLResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from server.api import templates
from server.core.constants import CLIENT_DISCONNECT

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: int):
        await websocket.accept()
        connections_for_room = self.active_connections.get(room_id, [])
        connections_for_room.append(websocket)
        self.active_connections[room_id] = connections_for_room

    def disconnect(self, websocket: WebSocket, room_id: int):
        if websocket in self.active_connections[room_id]:
            self.active_connections[room_id].remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str, room_id: int):
        for connection in self.active_connections[room_id]:
            await connection.send_text(message)


manager = ConnectionManager()


@router.get("", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.websocket("/{room_id}/{user_id}")
async def chat_room_connected(websocket: WebSocket, room_id: int, user_id: int):
    await manager.connect(websocket, room_id)
    # TODO : DB 에서 room_id & user_id 매핑 여부 확인 -> 매핑되어 있지 않을 시 브로드캐스트로 입장 메시지 송신
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"User #{user_id} says: {data}", room_id)
    except WebSocketDisconnect as e:
        # 반드시 웹소켓 연결 해제 후, 브로드캐스트 진행
        manager.disconnect(websocket, room_id)
        if e.code == CLIENT_DISCONNECT:
            await manager.broadcast(f"User #{user_id} left the chat", room_id)
