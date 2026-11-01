from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import UserModel
from app.auth.schemas import SetUserUsername, UserResponse
from app.core import logger
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/set-username",
    summary="Set the username on the current account",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    responses={
        409: {"description": "Username already taken"},
    },
)
async def set_username(
    data: SetUserUsername,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    TODO: Add rate limitting and tests

    Set or change the username on the signed-in account.

    **Endpoint:** POST `/auth/set-username`

    **Authentication:** `Authorization: Bearer <access_token>` required. The
    username is set on whoever the token identifies, so one user cannot rename
    another.

    Accounts created through Google start with no username, because Google does
    not supply one. This is how a user picks theirs, and how they change it
    later.

    ---

    ## Request Body (JSON)

    | Field      | Type   | Required | Validation                               |
    |------------|--------|----------|------------------------------------------|
    | `username` | string | Yes      | 3 to 30 characters; letters, numbers, underscores and hyphens;
    must start with a letter or number |

    ```json
    {
        "username": "vaporNimbus14"
    }
    ```

    ---

    ## Field Validation Rules

    ### username
    - Minimum 3 characters, maximum 30.
    - Surrounding whitespace is stripped before anything else runs.
    - Only letters, numbers, underscores, and hyphens are allowed. No spaces, no
      dots, no other punctuation.
    - Must start with a letter or a number, so a username cannot lead with `_`
      or `-`.
    - Compared case-insensitively against every other account: `Yassine` is
      taken if `yassine` exists. Stored with the capitalisation provided.

    ---

    ## Responses

    ### 200 OK
    The username was saved. The full updated account is returned, so the client
    can replace its cached profile without a second call to `/auth/me`.

    ```json
    {
        "id": "ca2b90d1-bc0a-4025-af81-1afb1c294a5b",
        "username": "vaporNimbus14",
        "name": "Yassine",
        "email": "yassine@example.com",
        "is_verified": true,
        "is_active": true,
        "auth_provider": "google"
    }
    ```

    ### 401 Unauthorized
    The access token is missing, expired, or not an access token.

    ```json
    {
        "detail": "Could not validate credentials."
    }
    ```

    ### 409 Conflict
    Another account already uses that username, ignoring case.

    ```json
    {
        "detail": "That username is already taken."
    }
    ```

    ### 422 Unprocessable Entity
    Pydantic rejected the body.

    ```json
    {
        "detail": [
            {
                "type": "value_error",
                "loc": ["body", "username"],
                "msg": "Value error, Username can only contain letters, numbers, underscores, and hyphens."
            }
        ]
    }
    ```

    Too short or too long fails on the length constraint instead, with `type` of
    `string_too_short` or `string_too_long`.

    ---

    ## Set Username Flow
    1. The bearer token is resolved to a user by `get_current_user`.
    2. Pydantic strips whitespace and validates the characters and length.
    3. The username is checked against other accounts case-insensitively. The
        caller's own row is excluded, so re-submitting the current username is
        not a conflict.
    4. The column is assigned and committed. The unique index is the final
        authority: if two requests race past step 3, the loser's commit raises
        `IntegrityError` and is turned into the same 409.
    """

    username = data.username

    taken = await db.scalar(
        select(select(UserModel.id).where(UserModel.username.ilike(username), UserModel.id != current_user.id).exists())
    )

    if taken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already taken.",
        )

    current_user.username = username

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already taken.",
        ) from e

    logger.info(f"User succesfully set username user id: {current_user.id}")

    return current_user
