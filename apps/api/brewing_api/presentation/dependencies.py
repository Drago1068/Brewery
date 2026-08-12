from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from brewing_api.application.auth import authenticate
from brewing_api.domain.identity.models import User
from brewing_api.platform.config import Settings, get_settings
from brewing_api.platform.database import get_db

Db = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def current_user(
    db: Db,
    settings: AppSettings,
    brewing_session: Annotated[str | None, Cookie()] = None,
) -> User:
    return authenticate(db, settings, brewing_session)


CurrentUser = Annotated[User, Depends(current_user)]

