from fastapi import status, HTTPException
from fastapi.exceptions import RequestValidationError

from server.core.enums import ResponseCode


class ClassifiableException(Exception):
    def __init__(self, code: ResponseCode, detail=None, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.code = code
        self.detail = code.value if not detail else detail
        self.status_code = status_code


class ExceptionHandler:
    base_err = {
        status.HTTP_400_BAD_REQUEST: ResponseCode.INVALID,
        status.HTTP_401_UNAUTHORIZED: ResponseCode.UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: ResponseCode.PERMISSION_DENIED,
        status.HTTP_404_NOT_FOUND: ResponseCode.NOT_FOUND,
        status.HTTP_405_METHOD_NOT_ALLOWED: ResponseCode.METHOD_NOT_ALLOWED,
    }

    def __init__(self, exc: Exception):
        self.exc = exc
        if isinstance(exc, ClassifiableException):
            self.code = exc.code
            self.error = exc.detail
        else:
            self.code = ResponseCode.INTERNAL_SERVER_ERROR
            for status_key in ("status", "status_code"):
                if hasattr(exc, status_key):
                    self.code = self.base_err.get(getattr(exc, status_key), self.code)
                    break
            if isinstance(exc, HTTPException):
                self.error = exc.detail
            elif isinstance(exc, RequestValidationError):
                self.error = exc.errors()
            else:
                self.error = str(exc)

    @property
    def status_code(self):
        return next(
            (k for k, v in self.base_err.items() if v == self.code), status.HTTP_500_INTERNAL_SERVER_ERROR)
