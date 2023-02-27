import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.templating import Jinja2Templates

from server.core.exceptions import ClassifiableException, ExceptionHandler

logger = logging.getLogger("websocket")

templates = Jinja2Templates(directory="templates")


class ExceptionHandlerRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except Exception as exc:
                exc_handler = ExceptionHandler(exc)
                logger.exception(exc_handler.error)
                raise ClassifiableException(
                    code=exc_handler.code,
                    detail=exc_handler.error,
                    status_code=exc_handler.status_code
                )

        return custom_route_handler
