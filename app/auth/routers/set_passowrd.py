from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import UserModel
from app.auth.schemas import SetUserPassword
from app.core import logger
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/set-password", summary="Set a password on the current account", status_code=status.HTTP_204_NO_CONTENT)
async def set_password(
    data: SetUserPassword,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    TODO: Add rate limitting and tests

    Set a password on the signed-in account.

    **Endpoint:** POST `/auth/set-password`

    **Authentication:** `Authorization: Bearer <access_token>` required. The
    password is set on whoever the token identifies — the account is never named
    in the request body, so one user cannot set another user's password.

    Accounts created through Google have no password: `password_hash` is null and
    `verify_password` returns False for them, so `/auth/login` cannot be used.
    This endpoint is what adds that second way in, leaving the account reachable
    if Google sign-in is ever unavailable.

    ---

    ## Request Body (JSON)

    | Field              | Type   | Required | Validation                                      |
    |--------------------|--------|----------|--------------------------------------------------|
    | `password`         | string | Yes      | 8–32 characters; at least one uppercase, one lowercase,
    one number, and one of `@$!%*?&` |
    | `confirm_password` | string | Yes      | 8–32 characters; must equal `password`           |

    Both fields are `SecretStr`, so neither is echoed back in an error response.

    ```json
    {
        "password": "Str0ng!Pass",
        "confirm_password": "Str0ng!Pass"
    }
    ```

    ---

    ## Responses

    ### 204 No Content
    The password was hashed with Argon2id and saved. There is no response body.

    Existing sessions are left alone — the refresh token in the browser stays
    valid, so the user is not signed out by setting a password.

    ### 401 Unauthorized
    The access token is missing, expired, or not an access token.

    ```json
    {
        "detail": "Could not validate credentials."
    }
    ```

    ### 422 Unprocessable Entity
    Pydantic rejected the body. Every rule above produces this shape, with `loc`
    naming the field that failed:

    ```json
    {
        "detail": [
            {
                "type": "value_error",
                "loc": ["body", "password"],
                "msg": "Value error, Password must contain at least one number."
            }
        ]
    }
    ```

    The match check runs on the whole model rather than one field, so it reports
    against the body itself:

    ```json
    {
        "detail": [
            {
                "type": "value_error",
                "loc": ["body"],
                "msg": "Value error, Passwords do not match."
            }
        ]
    }
    ```

    A password shorter than 8 or longer than 32 characters fails on the length
    constraint instead, with `type` of `string_too_short` or `string_too_long`.

    ---

    ## Set Password Flow
    1. The bearer token is resolved to a user by `get_current_user`.
    2. Pydantic validates strength and confirms the two fields match. Nothing in
        the handler re-checks this — a request that reaches the body has passed.
    3. `set_password` hashes the plaintext with Argon2id and assigns it. The raw
        password is never written anywhere, logged, or returned.
    4. The change is committed and 204 is returned.
    """

    password = data.password.get_secret_value()

    # hash and set user's password
    current_user.set_password(plaintext_password=password)

    # update auth provider
    current_user.auth_provider = "google_password"

    # Save
    await db.commit()

    logger.info(f"User succesfully set password user id: {current_user.id}")

    return
