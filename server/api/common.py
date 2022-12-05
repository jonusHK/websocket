from typing import Iterable, List, Dict, Any
from uuid import UUID

from aioredis import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket

from server.core.authentications import COOKIE_NAME, cookie, backend
from server.core.externals.redis.schemas import RedisFileBaseS
from server.models import User, S3Media


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


class RedisHandler:
    def __init__(self, redis: Redis):
        self.redis = redis

    @classmethod
    async def generate_presigned_files(cls, model, schema, iterable: Iterable):
        assert issubclass(model, S3Media), 'Invalid model type.'
        assert issubclass(schema, RedisFileBaseS), 'Invalid schema type.'

        files_s: List[schema] = []
        urls: List[Dict[str, Any]] = [
            r.result() for r in await model.asynchronous_presigned_url(*iterable)
        ]
        for m in iterable:
            model_to_dict = m.to_dict()
            model_to_dict.update({
                'url': next((u['url'] for u in urls if u['id'] == m.id), None)
            })
            files_s.append(schema(**model_to_dict))

        return files_s
