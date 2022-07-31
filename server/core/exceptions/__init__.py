from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from server.core.enums import ResponseCode
from server.main import app


class ClassifiableException(Exception):
    def __init__(self, code: ResponseCode, detail=None, status_code: int = status.HTTP_400_BAD_REQUEST):
        if not detail:
            detail = code.value

        self.code = code
        self.detail = detail
        self.status_code = status_code


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    base_err = {
        status.HTTP_400_BAD_REQUEST: ResponseCode.INVALID,
        status.HTTP_401_UNAUTHORIZED: ResponseCode.UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: ResponseCode.PERMISSION_DENIED,
        status.HTTP_404_NOT_FOUND: ResponseCode.NOT_FOUND,
        status.HTTP_405_METHOD_NOT_ALLOWED: ResponseCode.METHOD_NOT_ALLOWED,
    }

    if isinstance(exc, HTTPException):
        code = ResponseCode.NOT_FOUND
        data = exc.detail
    elif isinstance(exc, RequestValidationError):
        code = ResponseCode.INVALID
        data = exc.errors()
    elif isinstance(exc, ClassifiableException):
        code = exc.code
        data = exc.detail
    else:
        code = base_err.get(getattr(exc, 'status_code'), ResponseCode.INTERNAL_SERVER_ERROR)
        data = str(exc)

    err_data = code.retrieve()
    err_data.update({'data': data})

    kwargs = {
        'status_code': next((k for k, v in base_err.items() if v == code), status.HTTP_500_INTERNAL_SERVER_ERROR),
        'content': jsonable_encoder(err_data)
    }
    headers = getattr(exc, "headers", None)
    if headers:
        kwargs.update({'headers': headers})

    return JSONResponse(**kwargs)
