from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        type_: str = "about:blank",
        instance: str | None = None,
    ):
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type = type_
        self.instance = instance
        super().__init__(detail)


class ConflictError(AppError):
    def __init__(self, detail: str, instance: str | None = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT, title="Conflict", detail=detail, instance=instance
        )


class NotFoundError(AppError):
    def __init__(self, detail: str, instance: str | None = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            detail=detail,
            instance=instance,
        )


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Unauthorized", instance: str | None = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail=detail,
            instance=instance,
        )


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Forbidden", instance: str | None = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail=detail,
            instance=instance,
        )


def create_problem_response(
    request: Request, status_code: int, title: str, detail: str, type_: str = "about:blank"
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": type_,
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": str(request.url),
        },
        media_type="application/problem+json",
    )


async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "application_exception",
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        path=str(request.url),
    )
    return create_problem_response(request, exc.status_code, exc.title, exc.detail, exc.type)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning(
        "http_exception", status_code=exc.status_code, detail=exc.detail, path=str(request.url)
    )
    return create_problem_response(
        request,
        exc.status_code,
        exc.detail if isinstance(exc.detail, str) else "HTTP Error",
        str(exc.detail) if isinstance(exc.detail, str) else "HTTP Error",
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning("validation_exception", errors=exc.errors(), path=str(request.url))
    details = []
    for error in exc.errors():
        loc = " -> ".join(str(x) for x in error["loc"])
        details.append(f"{loc}: {error['msg']}")
    return create_problem_response(
        request, status.HTTP_422_UNPROCESSABLE_ENTITY, "Validation Error", "; ".join(details)
    )


async def pydantic_validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    logger.warning("pydantic_validation_exception", errors=exc.errors(), path=str(request.url))
    details = []
    for error in exc.errors():
        loc = " -> ".join(str(x) for x in error["loc"])
        details.append(f"{loc}: {error['msg']}")
    return create_problem_response(
        request, status.HTTP_422_UNPROCESSABLE_ENTITY, "Validation Error", "; ".join(details)
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning(
        "integrity_error", error=str(exc.orig) if exc.orig else str(exc), path=str(request.url)
    )
    return create_problem_response(
        request,
        status.HTTP_409_CONFLICT,
        "Conflict",
        "Resource conflict - possibly duplicate entry",
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", error=str(exc), path=str(request.url))
    return create_problem_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Internal Server Error",
        "An unexpected error occurred",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(IntegrityError, integrity_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)
