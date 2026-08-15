import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from fastapi import HTTPException, status
from google.auth.transport import requests as google_request
from google.oauth2 import id_token

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


def build_authorize_url(state: str) -> str:
    """Google consent-screen URL for the authorization-code flow."""

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": settings.GOOGLE_SCOPES,
        "access_type": "online",
        "prompt": "select_account",
        "state": state,
    }

    return f"{settings.GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_google_auth_for_token(token_data: dict[str, str]) -> tuple[str, str]:
    """
    Exchange a Google authorization code for the signed-in user's identity.

    This is the back-channel half of the authorization-code flow. The code that
    arrived on the callback is worthless on its own — it is redeemed here, in a
    direct server-to-server call carrying the client secret, which is why the
    secret never has to reach the browser.

    Google answers with an `id_token`: a JWT signed by Google asserting who the
    user is. It is verified rather than merely decoded, which checks the
    signature against Google's published keys, the issuer, the expiry, and that
    the `aud` claim is this application's client id. Skipping that check would
    let anyone mint an `id_token` for any email address.

    Args:
        token_data: Form fields for Google's token endpoint — `code`,
            `client_id`, `client_secret`, `redirect_uri`, and
            `grant_type=authorization_code`.

    Returns:
        The user's `email` and `name` from the verified token.

    Raises:
        HTTPException: 400 if Google rejects the exchange or returns no email,
            401 if the `id_token` fails verification.
    """

    async with httpx.AsyncClient() as client:
        token_response = await client.post(settings.GOOGLE_TOKEN_URL, data=token_data)

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google login error.",
            )

        tokens = token_response.json()

    try:
        user_info = id_token.verify_oauth2_token(
            tokens["id_token"], google_request.Request(), settings.GOOGLE_CLIENT_ID
        )

        # Extracted user details i need
        email = user_info.get("email").lower().strip()
        name = user_info.get("name").title().strip()
        email_verified = user_info.get("email_verified")

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google login error.",
        ) from e

    if not email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google login error.",
        )

    return email, name
