"""Password hashing and JWT issuing/verification.

Password hashing
----------------
bcrypt is used directly rather than through passlib (passlib 1.7.4 is
unmaintained and raises on bcrypt >= 4.1).

bcrypt silently truncates inputs at 72 bytes, which would make two long
passwords sharing a 72-byte prefix equivalent. We therefore pre-hash with
SHA-256 and base64-encode the digest before bcrypt — the well known
"bcrypt-sha256" construction. The digest is 44 base64 characters, comfortably
under the limit, and every byte of the original password contributes.

Tokens
------
Access tokens are short-lived, signed HS256 JWTs. The `role` claim is carried
for convenience/debugging only: authorisation ALWAYS re-reads the user and
their role from the database on every request (see app/dependencies.py), so a
tampered or stale token cannot grant privileges.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.config import get_settings

# bcrypt work factor. 12 is a reasonable default for current hardware; raise it
# as hardware improves. Configurable only so the test-suite can drop it — the
# floor below stops a misconfigured deployment from weakening real hashes.
MIN_BCRYPT_ROUNDS = 10


def _bcrypt_rounds() -> int:
    settings = get_settings()
    rounds = settings.bcrypt_rounds
    if not settings.is_production:
        return rounds
    return max(rounds, MIN_BCRYPT_ROUNDS)

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_COURT = "court_access"


class PasswordPolicyError(ValueError):
    """Raised when a proposed password does not meet the minimum policy."""


def _prehash(password: str) -> bytes:
    """SHA-256 + base64 so bcrypt never truncates meaningful input."""
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def validate_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password must be at most {MAX_PASSWORD_LENGTH} characters long."
        )
    classes = (
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    )
    if sum(classes) < 3:
        raise PasswordPolicyError(
            "Password must combine at least three of: lowercase, uppercase, digits, symbols."
        )


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the password. Never logs or returns the plaintext."""
    salt = bcrypt.gensalt(rounds=_bcrypt_rounds())
    return bcrypt.hashpw(_prehash(password), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time verification. Returns False rather than raising on bad input."""
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed stored hash — treat as a failed login, never as a success.
        return False


def create_access_token(
    *,
    subject: str,
    role: str,
    expires_minutes: int | None = None,
) -> tuple[str, int]:
    """Return `(token, expires_in_seconds)`."""
    settings = get_settings()
    minutes = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=minutes)

    claims: dict[str, Any] = {
        "sub": str(subject),
        "role": role,  # informational only — see module docstring
        "typ": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
        "iss": settings.app_name,
    }
    token = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, minutes * 60


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Verify signature/expiry and return the claims, or None if invalid.

    The algorithm allow-list is pinned to the configured algorithm so a token
    cannot downgrade itself (e.g. to `none`).
    """
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.app_name,
            options={"require": ["exp", "iat", "sub"]},
        )
    except InvalidTokenError:
        return None

    if claims.get("typ") != TOKEN_TYPE_ACCESS:
        return None
    return claims


def create_court_token(case_id: uuid.UUID, grant_id: uuid.UUID, expires_minutes: int) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expires_minutes)

    claims: dict[str, Any] = {
        "sub": str(grant_id),
        "case_id": str(case_id),
        "typ": TOKEN_TYPE_COURT,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
        "iss": settings.app_name,
    }
    token = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int((expires_at - now).total_seconds())

def decode_court_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.app_name,
            options={"require": ["exp", "iat", "sub", "case_id"]},
        )
    except InvalidTokenError:
        return None

    if claims.get("typ") != TOKEN_TYPE_COURT:
        return None
    return claims
