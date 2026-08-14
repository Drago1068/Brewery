import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def canonical_uuid(value: UUID | str) -> str:
    return str(value).lower()


def canonical_decimal(value: Decimal | int | str | None) -> str | None:
    if value is None:
        return None
    quantized = Decimal(str(value)).normalize()
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        text = "0"
    return text


def canonical_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    utc = value.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _transform(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _transform(value[key]) for key in sorted(value)}
    if isinstance(value, list | tuple):
        return [_transform(item) for item in value]
    if isinstance(value, UUID):
        return canonical_uuid(value)
    if isinstance(value, Decimal):
        return canonical_decimal(value)
    if isinstance(value, datetime):
        return canonical_datetime(value)
    return value


def canonical_document(value: Any) -> Any:
    return _transform(value)


def canonical_json(value: Any) -> str:
    return json.dumps(canonical_document(value), separators=(",", ":"), ensure_ascii=True)


def sha256_hex(value: str | bytes) -> str:
    payload = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def logical_plan_hash(document: Any) -> str:
    return sha256_hex(canonical_json(document))
