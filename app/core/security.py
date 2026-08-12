import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core import settings


def create_access_token(user_id: UUID) -> str:
    """
    Create a signed JWT access token for a user.

    Args:
        user_id: The user this token authenticates. Stored in the `sub` claim.

    Returns:
        The encoded JWT.
    """

    secret = settings.SECRET_KEY.get_secret_value()

    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "iat": datetime.now(UTC),
        "exp": expire,
        "type": "access",
    }

    encoded_jwt = jwt.encode(payload, secret, algorithm=settings.ALGORITHM)

    return encoded_jwt


def create_refresh_token() -> dict[str, str]:
    """
    Generate a new opaque refresh token.

    Returns both halves of the token:
        `raw` is sent to the client in an httpOnly
    cookie and never stored,
        `stored` is the SHA-256 hash persisted in
        `refresh_tokens.token_hash`.

    Unlike the access token this is not a JWT, it carries no claims. It is a
    random string whose meaning comes entirely from its database row, which is
    what makes it revocable.

    Returns:
        A dict with `raw` (give to the client) and `stored` (write to the database).
    """

    raw = secrets.token_urlsafe(48)
    stored = hashlib.sha256(raw.encode()).hexdigest()

    refresh = {"raw": raw, "stored": stored}

    return refresh


def set_refresh_cookie(response, raw_refresh: str):
    """Attach the refresh token to `response` as httpOnly cookie."""

    response.set_cookie(
        key="refresh",
        value=str(raw_refresh),
        max_age=settings.refresh_token_max_age,
        httponly=True,
        secure=settings.PRODUCTION,
        samesite="Lax",
        path="/auth",
    )


def delete_refresh_cookie(response) -> None:
    """Clear the refresh cookie, path/domain MUST match `set_refresh_cookie`."""

    response.delete_cookie(
        key="refresh",
        path="/auth",
    )
