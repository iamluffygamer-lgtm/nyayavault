"""Application exceptions and the handlers that turn them into API responses.

Error responses are deliberately terse. A caller learns that they may not do
something, never *why* — "case exists but you lack access" and "case does not
exist" both surface as 404, so the API cannot be used to probe for the existence
of cases the caller has no business knowing about.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected, client-facing failures."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_failed"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_failed"


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    code = "payload_too_large"


class UnsupportedMediaTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_media_type"


class IntegrityViolationError(AppError):
    """The stored bytes no longer match the recorded SHA-256."""

    status_code = status.HTTP_409_CONFLICT
    code = "integrity_violation"


def _body(code: str, message: str, request_id: str | None = None) -> dict:
    payload = {"error": {"code": code, "message": message}}
    if request_id:
        payload["error"]["request_id"] = request_id
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.info(
            "app_error",
            extra={"code": exc.code, "path": request.url.path, "request_id": request_id},
        )
        headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, exc.message, request_id),
            headers=headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=_body("http_error", str(exc.detail), request_id),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        payload = _body("validation_failed", "Request validation failed.", request_id)
        payload["error"]["details"] = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "issue": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content=payload)

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex
        # The driver message can leak schema details, so it is logged, not returned.
        logger.exception(
            "database_error", extra={"path": request.url.path, "request_id": request_id}
        )
        code = "conflict" if isinstance(exc, IntegrityError) else "database_error"
        status_code = 409 if isinstance(exc, IntegrityError) else 500
        return JSONResponse(
            status_code=status_code,
            content=_body(code, "The request could not be completed.", request_id),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex
        logger.exception(
            "unhandled_error", extra={"path": request.url.path, "request_id": request_id}
        )
        return JSONResponse(
            status_code=500,
            content=_body("internal_error", "An unexpected error occurred.", request_id),
        )
