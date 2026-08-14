import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from brewing_api.application.auth import ensure_bootstrap_user
from brewing_api.application.errors import DomainError
from brewing_api.application.phase3.csrf import Phase3SecurityMiddleware
from brewing_api.platform.config import get_settings
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.logging import configure_logging
from brewing_api.platform.metrics import (
    increment,
    new_correlation_id,
    reconstruct_failure,
    record_duration,
    snapshot,
)
from brewing_api.presentation.dependencies import CurrentUser
from brewing_api.presentation.routes import auth, brew_sessions, brewing_core, health, recipes

configure_logging()
log = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    with SessionLocal() as db:
        user = ensure_bootstrap_user(db, settings)
        log.info("bootstrap_user_ready", user_id=str(user.id), username=user.username)
    yield


app = FastAPI(
    title=settings.app_name,
    version="3.0.0-phase3",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Origin", "X-Correlation-ID"],
)
app.add_middleware(Phase3SecurityMiddleware)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    correlation_id = request.headers.get("x-correlation-id") or new_correlation_id()
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = record_duration(
        "http_request",
        started,
        correlation_id=correlation_id,
        ok=response.status_code < 500,
        method=request.method,
        path=request.url.path,
        status=str(response.status_code),
    )
    if response.status_code == 409:
        increment("command_conflict")
    if response.status_code == 403 and "csrf" in (response.headers.get("content-type") or ""):
        increment("csrf_rejected")
    response.headers["X-Correlation-ID"] = correlation_id
    log.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        correlation_id=correlation_id,
        duration_ms=round(duration_ms, 3),
    )
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    payload = {"detail": exc.message}
    if exc.code:
        payload["code"] = exc.code
    if exc.extra:
        payload.update(exc.extra)
    response = JSONResponse(status_code=exc.status_code, content=payload)
    if exc.status_code == 429 and "retry_after" in exc.extra:
        response.headers["Retry-After"] = str(exc.extra["retry_after"])
    return response


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Unexpected server error"})


@app.get("/api/v1/metrics/phase3")
def phase3_metrics(_user: CurrentUser) -> dict:
    return snapshot()


@app.get("/api/v1/metrics/phase3/reconstruct/{correlation_id}")
def phase3_reconstruct(correlation_id: str, _user: CurrentUser) -> dict:
    return {"correlation_id": correlation_id, "events": reconstruct_failure(correlation_id)}


app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(recipes.router, prefix="/api/v1")
app.include_router(brew_sessions.router, prefix="/api/v1")
app.include_router(brew_sessions.preview_router, prefix="/api/v1")
app.include_router(brewing_core.router, prefix="/api/v1")
