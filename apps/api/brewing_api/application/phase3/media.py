from __future__ import annotations

import hashlib
import os
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageFile, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import Response

from brewing_api.application.brew_day import get_session
from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit, journal
from brewing_api.application.phase3.operations import replay_or_conflict, store_success
from brewing_api.domain.brew_day.models import BrewAttachment
from brewing_api.domain.brew_sessions.models import BrewStage
from brewing_api.domain.identity.models import User
from brewing_api.platform.config import get_settings
from brewing_api.platform.time import utc_now

ALLOWED = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}
_PIL_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_FILE = 10 * 1024 * 1024
MAX_SESSION_COUNT = 20
MAX_SESSION_BYTES = 100 * 1024 * 1024
UNSAFE_MARKERS = (b"<svg", b"<html", b"<?xml", b"<script", b"%PDF")
MAX_DIMENSION = 20000
MAX_PIXELS = 20_000_000

ImageFile.LOAD_TRUNCATED_IMAGES = False
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def _media_root() -> Path:
    path = Path(get_settings().media_root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _magic_matches(declared: str, payload: bytes) -> bool:
    if declared == "image/webp":
        return len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP"
    return any(payload.startswith(marker) for marker in ALLOWED[declared])


def _decode_with_pillow(payload: bytes, declared: str) -> None:
    try:
        with Image.open(BytesIO(payload)) as probe:
            probe.verify()
        with Image.open(BytesIO(payload)) as image:
            image.load()
            if image.width < 1 or image.height < 1:
                raise DomainError("Image decoder rejected payload", 422, code="MEDIA_DECODE_FAILED")
            if image.width > MAX_DIMENSION or image.height > MAX_DIMENSION:
                raise DomainError("Image decoder rejected payload", 422, code="MEDIA_DECODE_FAILED")
            detected = _PIL_FORMATS.get(image.format)
            if detected != declared:
                raise DomainError(
                    "MIME and decoded format do not agree", 415, code="UNSUPPORTED_MEDIA"
                )
    except DomainError:
        raise
    except Image.DecompressionBombError as exc:
        raise DomainError(
            "Image exceeds bounded decoder limits", 422, code="MEDIA_DECODE_FAILED"
        ) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise DomainError(
            "Image decoder rejected payload", 422, code="MEDIA_DECODE_FAILED"
        ) from exc


def _sniff(declared: str, payload: bytes) -> str:
    lowered = payload[:200].lower()
    if any(marker in lowered for marker in UNSAFE_MARKERS):
        raise DomainError("Unsafe media content", 415, code="UNSUPPORTED_MEDIA")
    if declared not in ALLOWED:
        raise DomainError("MIME type is not allowed", 415, code="UNSUPPORTED_MEDIA")
    if not _magic_matches(declared, payload):
        raise DomainError("MIME and signature do not agree", 415, code="UNSUPPORTED_MEDIA")
    _decode_with_pillow(payload, declared)
    return declared


def _promote_bytes(payload: bytes, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.parent / f".tmp-{destination.name}-{uuid.uuid4().hex[:8]}"
    try:
        with open(temp_path, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    try:
        fd = os.open(destination, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass
    try:
        flags = getattr(os, "O_DIRECTORY", os.O_RDONLY)
        dir_fd = os.open(str(destination.parent), flags)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def upload_attachment(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    upload: UploadFile,
    operation_id: str,
    caption: str | None = None,
    stage_id: uuid.UUID | None = None,
) -> BrewAttachment:
    session = get_session(db, user, session_id)
    if session.status != "ACTIVE":
        raise ConflictError("Attachments can be uploaded only while the session is ACTIVE")
    if caption and len(caption) > 1000:
        raise DomainError("Caption must be at most 1000 characters", 422)
    raw_name = (upload.filename or "upload").replace("\\", "/")
    if ".." in raw_name or raw_name.startswith("/") or "/" in raw_name:
        raise DomainError("Unsafe filename", 422, code="UNSAFE_FILENAME")
    payload = upload.file.read()
    if len(payload) > MAX_FILE:
        raise DomainError("Attachment exceeds 10 MiB", 413, code="ATTACHMENT_TOO_LARGE")
    content_type = _sniff(upload.content_type or "", payload)
    checksum = hashlib.sha256(payload).hexdigest()
    if stage_id:
        stage = db.get(BrewStage, stage_id)
        if stage is None or stage.brew_session_id != session.id:
            raise DomainError(
                "stage_id does not belong to this session", 422, code="STAGE_OWNERSHIP"
            )
    document = {
        "filename": (upload.filename or "")[:255],
        "content_type": content_type,
        "caption": caption,
        "stage_id": str(stage_id) if stage_id else None,
        "sha256": checksum,
        "byte_length": len(payload),
    }
    replay = replay_or_conflict(
        db, user.id, "upload_attachment", "BrewSession", session.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewAttachment, replay.result_resource_id)
        if found:
            return found
    retained = list(
        db.scalars(
            select(BrewAttachment).where(
                BrewAttachment.brew_session_id == session.id,
                BrewAttachment.removed_at.is_(None),
            )
        ).all()
    )
    total_bytes = sum(item.byte_length for item in retained) + len(payload)
    if len(retained) >= MAX_SESSION_COUNT or total_bytes > MAX_SESSION_BYTES:
        raise ConflictError("Attachment quota exceeded", code="ATTACHMENT_QUOTA_EXCEEDED")
    storage_key = uuid.uuid4().hex
    destination = _media_root() / storage_key
    _promote_bytes(payload, destination)
    try:
        attachment = BrewAttachment(
            brew_session_id=session.id,
            stage_instance_id=stage_id,
            storage_key=storage_key,
            content_type=content_type,
            byte_length=len(payload),
            sha256=checksum,
            original_filename=raw_name[:255],
            caption=caption,
            actor_user_id=user.id,
            operation_id=operation_id,
        )
        db.add(attachment)
        db.flush()
        journal(
            db,
            session.id,
            "BREW_MEDIA_ATTACHED",
            "Photo attached",
            stage_id,
            {"attachment_id": str(attachment.id), "sha256": attachment.sha256},
            actor_id=user.id,
            operation_id=operation_id,
        )
        audit(db, user.id, "BREW_MEDIA_ATTACHED", "BrewAttachment", attachment.id)
        store_success(
            db,
            user.id,
            "upload_attachment",
            "BrewSession",
            session.id,
            operation_id,
            document,
            {"id": str(attachment.id), "status": attachment.status},
            "BrewAttachment",
            attachment.id,
        )
        db.commit()
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    db.refresh(attachment)
    return attachment


def retrieve_attachment(
    db: Session, user: User, session_id: uuid.UUID, attachment_id: uuid.UUID
) -> Response:
    session = get_session(db, user, session_id)
    attachment = db.scalar(
        select(BrewAttachment).where(
            BrewAttachment.id == attachment_id,
            BrewAttachment.brew_session_id == session.id,
        )
    )
    if attachment is None or attachment.removed_at is not None:
        raise NotFoundError("Attachment not found")
    path = _media_root() / attachment.storage_key
    if not path.is_file():
        raise DomainError("Media bytes are unavailable", 409, code="MEDIA_UNAVAILABLE")
    body = path.read_bytes()
    return Response(
        content=body,
        media_type=attachment.content_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="brew-photo-{attachment.id.hex[:8]}"',
            "Content-Length": str(len(body)),
        },
    )


def soft_remove_attachment(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    attachment_id: uuid.UUID,
    reason: str,
    operation_id: str | None,
) -> BrewAttachment:
    session = get_session(db, user, session_id)
    if session.status in {"COMPLETED", "ABORTED"}:
        raise ConflictError("Completed-session attachments cannot be removed")
    attachment = db.scalar(
        select(BrewAttachment).where(
            BrewAttachment.id == attachment_id,
            BrewAttachment.brew_session_id == session.id,
        )
    )
    if attachment is None:
        raise NotFoundError("Attachment not found")
    attachment.removed_at = utc_now()
    attachment.removal_reason = reason
    attachment.status = "REMOVED"
    journal(
        db,
        session.id,
        "BREW_MEDIA_REMOVED",
        "Photo removed before completion",
        attachment.stage_instance_id,
        {"attachment_id": str(attachment.id)},
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_MEDIA_REMOVED", "BrewAttachment", attachment.id)
    db.commit()
    db.refresh(attachment)
    return attachment


def reconcile_orphans(db: Session | None = None, max_age_hours: int = 24) -> int:
    from brewing_api.platform.database import SessionLocal

    root = _media_root()
    removed = 0
    cutoff = utc_now().timestamp() - max_age_hours * 3600
    if db is None:
        with SessionLocal() as owned:
            referenced = set(owned.scalars(select(BrewAttachment.storage_key)).all())
    else:
        referenced = set(db.scalars(select(BrewAttachment.storage_key)).all())
    if not root.exists():
        return 0
    for path in root.iterdir():
        if not path.is_file():
            continue
        if path.name.startswith(".tmp-"):
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
            continue
        if path.name not in referenced and path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    return removed


def session_attachment_bytes(db: Session, session_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(BrewAttachment.byte_length), 0)).where(
                BrewAttachment.brew_session_id == session_id,
                BrewAttachment.removed_at.is_(None),
            )
        )
        or 0
    )
