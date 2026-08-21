from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_or_create_google_user
from app.auth.models import RefreshTokenModel
from app.core import (
    create_refresh_token,
    exchange_google_auth_for_token,
    logger,
    set_refresh_cookie,
    settings,
)
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/google/callback", summary="Get redirect url for google login")
async def google_callback(
    db: Annotated[AsyncSession, Depends(get_db)],
    state: str | None = Cookie(None),
    code: str | None = Query(None),
    error: str | None = Query(None),
):
    """
    TODO: Add loggging, rate limitting and tests

    Finish the Google sign-in flow and hand the browser back to the frontend.

    **Endpoint:** GET `/auth/google/callback`

    **Authentication:** None required. This is where Google returns the user, so
    by definition they have no session yet. The `state` cookie set at the start
    of the flow is what proves the request is genuine.

    Not called by the frontend. Google redirects the browser here, so the
    response has to be another redirect rather than JSON — a user would
    otherwise be staring at a raw response body.

    ---

    ## Request

    | Source | Name    | Required | Description                                          |
    |--------|---------|----------|------------------------------------------------------|
    | Query  | `code`  | Yes      | Single-use authorization code issued by Google        |
    | Query  | `error` | No       | Present instead of `code` when the user declines      |
    | Cookie | `state` | Yes      | The value set when the flow started, echoed by Google |

    ---

    ## Responses

    ### 303 See Other
    Sign-in succeeded. The browser is sent to `FRONTEND_URL/auth/callback` with:

    - the `refresh` cookie set, httpOnly and scoped to `/auth`
    - the `state` cookie deleted, so it cannot be replayed

    No access token is included. It is not in the URL by design — query strings
    end up in browser history, referrer headers, and proxy logs. The frontend
    trades the refresh cookie for an access token on arrival, which is why it
    lands on a dedicated callback route rather than straight on the dashboard.

    ### 400 Bad Request
    The same body for every failure — consent declined, no code, missing or
    mismatched `state`, or Google rejecting the code exchange:

    ```json
    {
        "detail": "Google login error."
    }
    ```

    ### 401 Unauthorized
    Google returned an `id_token` that failed signature, issuer, audience, or
    expiry verification.

    ```json
    {
        "detail": "Google login error."
    }
    ```

    ---

    ## Callback Flow
    1. Reject the request unless a `code` and a `state` cookie are both present.
    2. Exchange the code for the user's identity in a direct server-to-server
        call carrying the client secret. The browser never sees it.
    3. Look up the user by verified email, creating the account on first sign-in.
    4. Mint an opaque refresh token, store its SHA-256 hash, and commit.
    5. Redirect to the frontend with the refresh cookie set and `state` cleared.

    ---

    ## Notes

    Both cookies are written on the `RedirectResponse` itself. Setting them on an
    injected `Response` would silently drop them, since FastAPI discards that
    object whenever the handler returns a response of its own.
    """

    if error or not code or not state:
        logger.error("User google loging error.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google login error.",
        )

    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET.get_secret_value(),
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    email, name = await exchange_google_auth_for_token(token_data=token_data)
    user_data = await get_or_create_google_user(email, name, db)

    # generate jwt token pair
    refresh_token = create_refresh_token()

    # save refresh
    db.add(
        RefreshTokenModel(
            user_id=user_data.id,
            token_hash=refresh_token["stored"],
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await db.commit()

    # redirect, return user info w access, set cookie nd del state
    redirect = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback",
        status_code=status.HTTP_303_SEE_OTHER,
    )

    # del state cookie
    redirect.delete_cookie(key="state", path="/auth")

    # refresh in http only cookie
    set_refresh_cookie(redirect, refresh_token["raw"])

    return redirect
