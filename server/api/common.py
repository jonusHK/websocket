from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket

from server.core.authentications import COOKIE_NAME, cookie, backend
from server.models import User


class AuthValidator:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_websocket(self, websocket: WebSocket) -> User:
        signed_session_id = websocket.cookies[COOKIE_NAME]
        session_id = UUID(
            cookie.signer.loads(
                signed_session_id,
                max_age=cookie.cookie_params.max_age,
                return_timestamp=False,
            )
        )
        user_session = await backend.read(session_id, self.session)
        user = user_session.user
        return user
