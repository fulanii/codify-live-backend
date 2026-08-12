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
    TODO: Add loggging, rate limitting and tests

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
