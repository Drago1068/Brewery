from typing import Annotated

from fastapi import APIRouter, Cookie, Response

from brewing_api.application import auth as auth_service
from brewing_api.application.events import audit
from brewing_api.presentation.dependencies import AppSettings, CurrentUser, Db
from brewing_api.presentation.schemas import LoginRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["identity"])


@router.post("/login", response_model=UserResponse)
def login(command: LoginRequest, response: Response, db: Db, settings: AppSettings) -> UserResponse:
    user, token = auth_service.login(db, settings, command.username, command.password)
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
    return UserResponse.model_validate(user)


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
