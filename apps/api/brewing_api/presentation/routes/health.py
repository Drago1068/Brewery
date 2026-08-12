from fastapi import APIRouter, HTTPException
from redis import Redis
from sqlalchemy import text

from brewing_api.platform.config import get_settings
from brewing_api.presentation.dependencies import Db

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Db) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        Redis.from_url(get_settings().redis_url, socket_timeout=1).ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dependency readiness check failed") from exc
    return {"status": "ready"}

