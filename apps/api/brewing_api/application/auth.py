import hashlib
import secrets
from datetime import timedelta

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import DomainError
from brewing_api.application.phase3.tokens import csrf_digest, generate_csrf_token
from brewing_api.domain.identity.models import AuthSession, User
from brewing_api.platform.config import Settings
from brewing_api.platform.time import utc_now

password_hash = PasswordHash.recommended()


def token_digest(token: str, secret: str) -> str:
    return hashlib.sha256(f"{secret}:{token}".encode()).hexdigest()


def ensure_bootstrap_user(db: Session, settings: Settings) -> User:
    user = db.scalar(select(User).where(User.username == settings.bootstrap_admin_username))
    if user is None:
        user = User(
            username=settings.bootstrap_admin_username,
            password_hash=password_hash.hash(settings.bootstrap_admin_password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def login(db: Session, settings: Settings, username: str, password: str) -> tuple[User, str, str]:
    user = db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
    if user is None or not password_hash.verify(password, user.password_hash):
        raise DomainError("Invalid username or password", 401)
    token = secrets.token_urlsafe(48)
    session = AuthSession(
        user_id=user.id,
        token_hash=token_digest(token, settings.session_secret),
        expires_at=utc_now() + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    db.flush()
    csrf = generate_csrf_token()
    session.csrf_token_hash = csrf_digest(csrf, settings.session_secret)
    db.commit()
    return user, token, csrf


def authenticate(db: Session, settings: Settings, token: str | None) -> User:
    if not token:
        raise DomainError("Authentication required", 401)
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_digest(token, settings.session_secret),
            AuthSession.expires_at > utc_now(),
        )
    )
    if session is None:
        raise DomainError("Session is invalid or expired", 401)
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise DomainError("User is inactive", 403)
    return user


def logout(db: Session, settings: Settings, token: str | None) -> None:
    if token:
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == token_digest(token, settings.session_secret)
            )
        )
        if session:
            db.delete(session)
            db.commit()
