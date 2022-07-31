from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from server.core.enums import ResponseCode
from server.main import app


def convert_err_data(err_data: Any):
    return {
        "response": 0,
        "error": jsonable_encoder(err_data)
    }


class ClassifiableException(Exception):
    def __init__(self, code: ResponseCode, detail=None, status_code: int = status.HTTP_400_BAD_REQUEST):
        if not detail:
            detail = code.value

        self.code = code
        self.detail = detail
        self.status_code = status_code


@app.exception_handler(ClassifiableException)
async def classifiable_exception_handler(request: Request, exc: ClassifiableException):
    return JSONResponse(
        status_code=exc.status_code,
        content=convert_err_data(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=convert_err_data(exc.errors()))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    headers = getattr(exc, "headers", None)
    kwargs = {'status_code': exc.status_code, 'content': convert_err_data(exc.detail)}
    if headers:
        kwargs.update({'headers': headers})
    return JSONResponse(**kwargs)
