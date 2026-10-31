"""FastAPI application factory."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import Settings, get_settings
from app.container import Container, build_container
from app.core.errors import AppError
from app.core.logging import configure_logging, request_id_var

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        container.db.create_schema()  # dev convenience; production uses `alembic upgrade head`
        yield

    app = FastAPI(
        title="Merchant AI Teammate API",
        description="A demo merchant-support teammate using SIMULATED Paytm-style integrations. "
                    "No production Paytm APIs or systems are connected.",
        version="0.2.0", lifespan=lifespan,
    )
    app.state.container = container
    app.include_router(router)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-Id"] = rid
        return response

    @app.exception_handler(AppError)
    async def app_error(_r: Request, exc: AppError):
        status = 503 if exc.message == "database unavailable" else exc.status_code
        return JSONResponse(status_code=status,
                            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(Exception)
    async def unhandled(_r: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse(status_code=500, content={"error": {
            "code": "internal_error", "message": "Internal server error"}})

    return app


def app_factory() -> FastAPI:  # uvicorn app.main:app_factory --factory
    return create_app()
