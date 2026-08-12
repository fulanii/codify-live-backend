import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshTokenModel
from app.auth.schemas import NewAccessToken
from app.core import (
    create_access_token,
    create_refresh_token,
    set_refresh_cookie,
    settings,
)
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/refresh",
    summary="Get new access token",
    response_model=NewAccessToken,
    status_code=status.HTTP_200_OK,
)
async def refresh_access_token(request: Request, response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    TODO: Add loggging, rate limitting and tests

    Exchange the refresh cookie for a new access token, rotating the refresh token.

    **Endpoint:** POST `/auth/refresh`

    **Authentication:** None required. The session is identified by the httpOnly
    `refresh` cookie. No `Authorization` header is read — the client calls this
    endpoint precisely when its access token is gone or expired, so requiring one
    would deadlock the session.

    ---

    ## Request

    No body. The browser sends the `refresh` cookie automatically, provided the
    request is made with credentials included and the path is under `/auth`.

    | Cookie  | Type   | Required | Description                              |
    |---------|--------|----------|------------------------------------------|
    | refresh | string | Yes      | The opaque refresh token issued at login |

    ---

    ## Responses

    ### 200 OK
    The token was valid. It is now revoked and replaced: a new refresh token is set
    as a cookie and a new access token is returned in the body.

    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```

    ### 401 Unauthorized
    Returned for every failure mode with an identical body, so the response cannot
    be used to learn whether a given token ever existed:

    - the cookie is absent
    - no row matches the token's hash
    - the token has expired
    - the token was already revoked (see below)

    ```json
    {
        "detail": "Invalid or expired session."
    }
    ```

    The client's response is the same in all four cases: discard local state and
    send the user to log in.

    ---

    ## Rotation and reuse detection

    Every successful refresh revokes the presented token and issues a new one.
    Revoked rows are kept rather than deleted, which is what makes replay
    detectable.

    A token that is presented *after* it has been revoked means two parties hold
    the same token — a stolen cookie, or a client that fired two refreshes at once.
    Since the legitimate holder and the attacker cannot both succeed, the second
    presentation is treated as a compromise: every refresh token belonging to that
    user is revoked, ending all their sessions, and the request fails with 401.

    ---

    ## Refresh Flow
    1. The `refresh` cookie is read; a missing cookie is a 401.
    2. The token is hashed with SHA-256 and its row looked up by digest.
    3. Expiry and revocation are checked. A revoked token triggers the mass
        revocation described above.
    4. The presented token is revoked and a replacement row is inserted for the
        same user, with a lifetime of `REFRESH_TOKEN_EXPIRE_DAYS`.
    5. A new access token is minted from the row's `user_id`. No user lookup is
        needed — the refresh row already carries the identity.
    6. The new refresh token is set as an httpOnly cookie and the access token is
        returned in the body, where the client holds it in memory only.
    """

    # grab the refresh cookie
    refresh_cookie = request.cookies.get("refresh")
    if refresh_cookie is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    # hash it so we can search it (only has is stored)
    refresh_hash = hashlib.sha256(refresh_cookie.encode()).hexdigest()

    # build query, execute and grab result
    query = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == refresh_hash)
    row = await db.execute(query)
    refresh_data = row.scalar_one_or_none()

    if refresh_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    # Someone is presenting it a second time, which means either a stolen token or a client bug
    # so revoke eveything :)
    if refresh_data.is_revoked:
        refresh_tokens_query = select(RefreshTokenModel).where(RefreshTokenModel.user_id == refresh_data.user_id)
        refresh_token_rows = await db.execute(refresh_tokens_query)
        all_user_refresh_tokens = refresh_token_rows.scalars.all()

        for refresh_token in all_user_refresh_tokens:
            refresh_token.is_revoked = True

        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    if refresh_data.is_expired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    refresh_data.is_revoked = True

    # generate jwt token pair
    access_token = create_access_token(refresh_data.user_id)
    refresh_token = create_refresh_token()

    db.add(
        RefreshTokenModel(
            user_id=refresh_data.user_id,
            token_hash=refresh_token["stored"],
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await db.commit()

    # refresh in http only cookie
    set_refresh_cookie(response, refresh_token["raw"])

    res_data = {"access_token": access_token}

    return res_data
