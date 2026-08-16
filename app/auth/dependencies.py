import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserModel
from app.core.config import settings
from app.db import get_db

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserModel:
    """
    Resolve the bearer access token into the user it authenticates.

    Args:
        credentials: The `Authorization: Bearer <token>` header, parsed by `HTTPBearer`.
        db: Database session.

    Returns:
        The `UserModel` named by the token's `sub` claim.

    Raises:
        HTTPException: 401 if the token is malformed, expired, not an access
            token, or no longer matches an active user. 403 if the account is
            inactive.
    """

    secret = settings.SECRET_KEY.get_secret_value()

    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # A refresh token presented as a bearer token must not be accepted.
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(sub)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    query = select(UserModel).where(UserModel.id == user_id)
    row = await db.execute(query)
    user = row.scalar_one_or_none()

    # The token is signed but the user was deleted since it was issued.
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_or_create_google_user(email: str, name: str, db):
    """
    Find the user behind a verified Google identity, creating them on first login.

    Google sign-in doubles as registration: there is no separate signup step, so
    the first time an email arrives it becomes an account. Matching is by email,
    which is safe only because the caller has already verified the `id_token`
    and checked `email_verified` — an unverified address would let someone claim
    an account that is not theirs.

    New users are created with `is_verified=True` (Google has already proven the
    address) and no password. `password_hash` stays null until they choose to set
    one, and `verify_password` returns False for those users, so a null hash can
    never be logged into.

    Args:
        email: Verified email address from the Google `id_token`.
        name: Display name from the same token.
        db: Database session.

    Returns:
        The existing or newly created user.
    """

    query = select(UserModel).where(UserModel.email == email)
    row = await db.execute(query)
    user = row.scalar_one_or_none()

    # new user
    if user is None:
        user = UserModel(name=name, email=email, is_verified=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
