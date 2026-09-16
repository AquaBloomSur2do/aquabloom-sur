from fastapi import Request
from fastapi.responses import JSONResponse

from .auth import AuthException
from .schemas import ErrorResponse


async def global_exception_handler(request: Request, exc: Exception):
    error_content = ErrorResponse(error="InternalServerError", message=str(exc))
    return JSONResponse(status_code=500, content=error_content.model_dump())

async def auth_exception_handler(request: Request, exc: AuthException):
    error_content = ErrorResponse(
        error="Unauthorized",
        message=exc.message,
        details=exc.details
    )
    return JSONResponse(
        status_code=401,
        content=error_content.model_dump()
    )
