"""FastAPI application factory.

Modular monolith: one deployable process, clear internal seams
(routers -> services -> models). No microservices.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.errors import register_exception_handlers
from app.logging_config import configure_logging
from app.routers import audit, auth, cases, documents, users, evidence, search, departments
from app.storage import StorageError, get_storage

logger = logging.getLogger(__name__)

DESCRIPTION = """
Secure, case-centric document and evidence management for legal and
investigation workflows (SIH problem statement 26190).

**Milestone 0 — foundation.** Implemented: authentication, role-based and
case-level authorisation, case management, versioned document storage with
SHA-256 integrity verification, and a hash-linked audit trail.

Not yet implemented: OCR, semantic search, AI metadata extraction, digital
signatures, evidence workflows and court-package generation.

This is a prototype. It is **not** production-hardened — see SECURITY.md.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info(
        "starting",
        extra={"app": settings.app_name, "version": __version__, "env": settings.app_env},
    )
    try:
        # get_storage() reuses a backend that has already been injected (the
        # test-suite does this) and otherwise builds the MinIO client.
        get_storage().ensure_bucket()
    except StorageError as exc:
        # Fail loudly rather than accepting uploads we cannot store.
        logger.error("object_storage_unavailable", extra={"error": str(exc)})
        raise

    yield
    logger.info("shutting_down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=f"{settings.app_name} API",
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # Explicit origin allow-list. Credentials are not sent as cookies (the token
    # travels in the Authorization header), so allow_credentials stays off.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID", "X-Document-SHA256", "X-Document-Version"],
        max_age=600,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        """Attach a request id, time the call, and set baseline security headers."""
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
                "user_id": getattr(request.state, "user_id", None),
            },
        )
        return response

    register_exception_handlers(app)

    prefix = settings.api_v1_prefix
    app.include_router(auth.router, prefix=prefix)
    app.include_router(users.router, prefix=prefix)
    app.include_router(cases.router, prefix=prefix)
    app.include_router(documents.router, prefix=prefix)
    app.include_router(audit.router, prefix=prefix)
    app.include_router(evidence.router, prefix=prefix)
    app.include_router(search.router, prefix=prefix)


    @app.get("/health", tags=["System"], summary="Liveness probe")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
