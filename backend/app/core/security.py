from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.core.errors import UnauthorizedError
from app.core.settings import get_settings

_PBKDF2_ALGO = "sha256"
_PBKDF2_ROUNDS = 390000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGO,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ROUNDS,
    ).hex()
    return f"pbkdf2_{_PBKDF2_ALGO}${_PBKDF2_ROUNDS}${salt}${digest}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        scheme, rounds, salt, expected_digest = password_hash.split("$", 3)
        if not scheme.startswith("pbkdf2_"):
            return False
        computed = hashlib.pbkdf2_hmac(
            _PBKDF2_ALGO,
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            int(rounds),
        ).hex()
        return hmac.compare_digest(computed, expected_digest)
    except ValueError:
        return False


def create_access_token(subject: str, *, is_guest: bool, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    expire_at = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "is_guest": is_guest,
        "exp": int(expire_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
