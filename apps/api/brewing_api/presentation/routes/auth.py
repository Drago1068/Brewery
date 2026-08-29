from typing import Annotated

from fastapi import APIRouter, Cookie, Response

from brewing_api.application import auth as auth_service
from brewing_api.application.events import audit
from brewing_api.presentation.dependencies import AppSettings, CurrentUser, Db
from brewing_api.presentation.schemas import LoginRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["identity"])


@router.post("/login")
def login(command: LoginRequest, response: Response, db: Db, settings: AppSettings) -> dict:
    user, token, csrf = auth_service.login(db, settings, command.username, command.password)
    response.set_cookie(
        "brewing_session",
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    audit(db, user.id, "USER_LOGGED_IN", "User", user.id)
    db.commit()
    return {"id": str(user.id), "username": user.username, "csrf_token": csrf}


@router.get("/csrf")
def csrf(
    user: CurrentUser,
    db: Db,
    settings: AppSettings,
    brewing_session: Annotated[str | None, Cookie()] = None,
) -> dict:
    from sqlalchemy import select

    from brewing_api.application.auth import token_digest
    from brewing_api.application.phase3.tokens import csrf_digest, generate_csrf_token
    from brewing_api.domain.identity.models import AuthSession
    from brewing_api.platform.time import utc_now

    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_digest(brewing_session or "", settings.session_secret),
            AuthSession.expires_at > utc_now(),
        )
    )
    if session is None:
        from brewing_api.application.errors import DomainError

        raise DomainError("Authentication required", 401)
    token = generate_csrf_token()
    session.csrf_token_hash = csrf_digest(token, settings.session_secret)
    db.commit()
    return {"csrf_token": token}


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Db,
    settings: AppSettings,
    user: CurrentUser,
    brewing_session: Annotated[str | None, Cookie()] = None,
) -> None:
    auth_service.logout(db, settings, brewing_session)
    response.delete_cookie("brewing_session", path="/")
    audit(db, user.id, "USER_LOGGED_OUT", "User", user.id)
    db.commit()


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
