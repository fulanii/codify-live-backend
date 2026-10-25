import secrets
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
    state_cookie: str | None = Cookie(None, alias="state"),
    error: str | None = Query(None),
    code: str | None = Query(None),
    state: str | None = Query(None),
):
    """
    TODO: Add rate limitting

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
    The same body for every failure — consent declined, no code, a missing
    `state` cookie, a `state` that does not match, or Google rejecting the code
    exchange:

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
    1. Reject the request unless Google sent a `code` and a `state`, and the
        browser sent back the `state` cookie. Each is checked separately: a
        missing cookie has to fail here rather than reach the comparison below,
        which raises on `None` rather than returning False.
    2. Compare the two `state` values in constant time. They match only if this
        browser is the one that started the flow, which is what stops an attacker
        from feeding a victim a callback URL carrying their own `code` and
        silently signing the victim into the attacker's account.
    3. Exchange the code for the user's identity in a direct server-to-server
        call carrying the client secret. The browser never sees it.
    4. Look up the user by verified email, creating the account on first sign-in.
    5. Mint an opaque refresh token, store its SHA-256 hash, and commit.
    6. Redirect to the frontend with the refresh cookie set and `state` cleared.

    ---

    ## Notes

    Both cookies are written on the `RedirectResponse` itself. Setting them on an
    injected `Response` would silently drop them, since FastAPI discards that
    object whenever the handler returns a response of its own.

    The `state` comparison uses `secrets.compare_digest` rather than `==`, which
    short-circuits on the first differing byte and leaks the matching prefix
    through response timing.
    """

    if error or not code or not state:
        logger.error("User google loging error.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google login error.",
        )

    if not state_cookie:
        logger.error("State cookie missing.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google login error.",
        )

    if not secrets.compare_digest(state, state_cookie):
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

    logger.info(f"Google login succesful user id: {user_data.id}")

    return redirect
