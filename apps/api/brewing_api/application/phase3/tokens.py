import hashlib
import hmac
import secrets
from uuid import UUID


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def derive_csrf_token(auth_session_id: UUID, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        f"csrf-v1:{auth_session_id}".encode(),
        hashlib.sha256,
    ).digest()
    return digest.hex()


def csrf_digest(token: str, secret: str) -> str:
    return hashlib.sha256(f"{secret}:csrf:{token}".encode()).hexdigest()
