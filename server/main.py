import asyncio
import typing
from time import time

import uvicorn
from fastapi import FastAPI, Request
from starlette.endpoints import WebSocketEndpoint
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocket

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# @app.websocket("/chat")
# async def chat(websocket: WebSocket):
#     await websocket.accept()
#     while True:
#         data = await websocket.receive_text()
#         await websocket.send_text(f"Message: {data}")


@app.websocket_route("/chat")
class WebSocketChat(WebSocketEndpoint):
    async def on_connect(self, websocket):
        await websocket.accept()
        self.last_time = time()
        print(f"[{self.last_time}] connected: {websocket.client}")

    async def on_receive(self, websocket: WebSocket, data) -> None:
        await websocket.send_text(data)
        self.last_time = time()
        print(f"[{self.last_time}] {data}")

    async def on_disconnect(self, websocket, close_code):
        print(f"[{time()}] disconnected: {websocket.client}")
        print("delay:", time() - self.last_time)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
