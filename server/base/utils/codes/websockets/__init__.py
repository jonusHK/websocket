from starlette.websockets import WebSocketDisconnect


class ClientDisconnect(WebSocketDisconnect):
    code = 4000

    def __init__(self):
        self.code = ClientDisconnect.code
