from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.db.session import engine


async def check_postgres() -> dict:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001 — readiness must never raise
        return {"status": "error", "detail": str(exc)}


def check_storage() -> dict:
    """Verify configured persistent paths exist and are writable."""
    targets = {
        "storage_path": settings.storage_path,
        "log_path": settings.log_path,
    }
    details: dict[str, str] = {}
    try:
        for label, raw in targets.items():
            path = Path(raw)
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".brewingos-write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            details[label] = str(path.resolve())
        return {"status": "ok", "paths": details}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc), "paths": details}
