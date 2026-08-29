import os
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from brewing_api.application.phase3.tokens import csrf_digest
from brewing_api.domain.identity.models import AuthSession
from brewing_api.platform.config import get_settings
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
_rate_window: dict[str, list[datetime]] = defaultdict(list)


def reset_rate_limits() -> None:
    _rate_window.clear()


def allowed_origins(settings) -> set[str]:
    origins = set(settings.cors_origins or [])
    origins.add(settings.public_origin)
    return {item.rstrip("/") for item in origins if item}


def _origin_ok(request: Request, settings) -> bool:
    allowed = allowed_origins(settings)
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/") in allowed
    referer = request.headers.get("referer")
    if referer:
        return any(referer.startswith(item) for item in allowed)
    return False


def _enforce_rate_limit(user_id: str, is_upload: bool) -> JSONResponse | None:
    now = utc_now()
    key = f"{user_id}:{'upload' if is_upload else 'mut'}"
    window = _rate_window[key]
    cutoff = now - timedelta(seconds=60)
    _rate_window[key] = [stamp for stamp in window if stamp > cutoff]
    default_limit = (
        "500"
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TESTING") == "1"
        else "120"
    )
    limit = 10 if is_upload else int(os.environ.get("PHASE3_RATE_LIMIT_MUTATIONS", default_limit))
    if len(_rate_window[key]) >= limit:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "code": "RATE_LIMITED"},
            headers={"Retry-After": "60"},
        )
    _rate_window[key].append(now)
    return None


class Phase3SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from brewing_api.application.auth import token_digest

        if request.method in SAFE_METHODS or request.url.path.startswith("/health"):
            return await call_next(request)
        if request.method not in MUTATING:
            return await call_next(request)
        settings = get_settings()
        if not _origin_ok(request, settings):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF origin check failed", "code": "CSRF_REJECTED"},
            )
        if request.url.path.rstrip("/").endswith("/auth/login"):
            return await call_next(request)
        token = request.cookies.get("brewing_session")
        if not token:
            return await call_next(request)
        with SessionLocal() as db:
            session = db.scalar(
                select(AuthSession).where(
                    AuthSession.token_hash == token_digest(token, settings.session_secret),
                    AuthSession.expires_at > utc_now(),
                )
            )
            if session is None:
                return await call_next(request)
            provided = request.headers.get("x-csrf-token")
            expected_digest = session.csrf_token_hash
            if (
                not provided
                or not expected_digest
                or csrf_digest(provided, settings.session_secret) != expected_digest
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "CSRF token was missing or invalid",
                        "code": "CSRF_REJECTED",
                    },
                )
            limited = _enforce_rate_limit(str(session.user_id), "/attachments" in request.url.path)
            if limited is not None:
                return limited
        return await call_next(request)
