import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core import settings


def create_access_token(user_id: UUID, expires_delta: timedelta | None = None) -> str:
    """
    Create a signed JWT access token for a user.

    Args:
        user_id: The user this token authenticates. Stored in the `sub` claim.
        expires_delta: How long the token stays valid. Defaults to 15 minutes.

    Returns:
        The encoded JWT.
    """

    secret = settings.SECRET_KEY.get_secret_value()

    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=15))

    payload = {
        "sub": str(user_id),
        "iat": datetime.now(UTC),
        "exp": expire,
        "type": "access",
    }

    encoded_jwt = jwt.encode(payload, settings=secret, algorithm=settings.ALGORITHM)

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
