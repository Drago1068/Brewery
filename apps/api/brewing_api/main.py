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
    allow_headers=["Content-Type", "X-CSRF-Token", "Origin"],
)
app.add_middleware(Phase3SecurityMiddleware)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    response = await call_next(request)
    log.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
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


app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(recipes.router, prefix="/api/v1")
app.include_router(brew_sessions.router, prefix="/api/v1")
app.include_router(brew_sessions.preview_router, prefix="/api/v1")
app.include_router(brewing_core.router, prefix="/api/v1")
