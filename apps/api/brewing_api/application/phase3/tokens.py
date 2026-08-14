import hashlib
import hmac
from uuid import UUID


def derive_csrf_token(auth_session_id: UUID, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        f"csrf-v1:{auth_session_id}".encode(),
        hashlib.sha256,
    ).digest()
    return digest.hex()


def csrf_digest(token: str, secret: str) -> str:
    return hashlib.sha256(f"{secret}:csrf:{token}".encode()).hexdigest()
