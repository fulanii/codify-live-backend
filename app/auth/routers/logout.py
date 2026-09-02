import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshTokenModel
from app.core import delete_refresh_cookie
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user refresh cookie",
)
async def logout(request: Request, response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    TODO: Add rate limitting and tests

    Log the current session out.

    **Endpoint:** POST `/auth/logout`

    **Authentication:** None required. The session is identified by the `refresh`
    cookie, not by a bearer token, so an expired access token does not prevent
    logging out.

    ---

    ## Request

    No body. The browser sends the httpOnly `refresh` cookie automatically,
    provided the request is made with credentials included.

    | Cookie  | Type   | Required | Description                                        |
    |---------|--------|----------|----------------------------------------------------|
    | refresh | string | No       | The opaque refresh token issued at login            |

    ---

    ## Responses

    ### 204 No Content
    The session has been ended. There is no response body.

    The response is intentionally identical whether the cookie was missing,
    unrecognised, or already revoked, so the endpoint cannot be used to probe
    whether a given token is still live. Logging out twice is not an error.

    ---

    ## Logout Flow
    1. The `refresh` cookie is read from the request.
    2. The cookie is cleared with a matching `path`, so the browser removes it
        rather than storing a second copy.
    3. The token is hashed with SHA-256 and its row looked up. Only the hash is
        stored, so the lookup is by digest rather than by the token itself.
    4. The row is marked revoked and committed. This is the step that actually
        ends the session: clearing the cookie only makes the browser forget its
        copy, while revocation invalidates the token for anyone holding it.
    5. The client discards its in-memory access token. That token stays
        cryptographically valid until it expires, which is why the access token
        lifetime is kept short.
    """

    delete_refresh_cookie(response)

    refresh_cookie = request.cookies.get("refresh")
    if refresh_cookie is None:
        return

    # find store refresh and revoke
    refresh_hash = hashlib.sha256(refresh_cookie.encode()).hexdigest()

    query = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == refresh_hash)
    row = await db.execute(query)

    refresh_data = row.scalar_one_or_none()
    if refresh_data is None:
        return

    refresh_data.is_revoked = True

    await db.commit()

    return
