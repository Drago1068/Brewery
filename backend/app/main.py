from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.db.session import engine
from app.health import check_postgres, check_storage
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)


def ensure_runtime_dirs() -> None:
    for path in (settings.storage_path, settings.log_path):
        Path(path).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging(settings.log_level)
    ensure_runtime_dirs()
    logger.info(
        "BrewingOS API starting (env=%s, storage=%s)",
        settings.brewingos_env,
        settings.storage_path,
    )
    yield
    logger.info("BrewingOS API shutting down")
    await engine.dispose()


app = FastAPI(
    title="BrewingOS",
    description="Brewing Intelligence & Competition OS — Epic 1 Foundation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_liveness():
    """Process is up. Does not check dependencies."""
    return {
        "status": "ok",
        "service": "brewingos-api",
        "version": "0.1.0",
        "environment": settings.brewingos_env,
        "epic": 1,
        "increment": 5,
    }


@app.get("/health/ready")
async def health_readiness(response: Response):
    """Checks Postgres and persistent storage paths."""
    postgres = await check_postgres()
    storage = check_storage()
    checks = {"postgres": postgres, "storage": storage}
    all_ok = all(check["status"] == "ok" for check in checks.values())

    payload = {
        "status": "ok" if all_ok else "degraded",
        "service": "brewingos-api",
        "checks": checks,
    }

    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return payload
