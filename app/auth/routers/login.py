from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.auth.models import RefreshTokenModel, UserModel
from app.auth.schemas import UserLoginRequest, UserLoginResponse
from app.core import (
    create_access_token,
    create_refresh_token,
    set_refresh_cookie,
    settings,
)
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=UserLoginResponse,
    summary="Log in with email and password",
    responses={
        401: {"description": "Invalid credentials"},
        403: {"description": "Account is unverified or deactivated"},
    },
)
async def login(login_data: UserLoginRequest, response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    Authenticate a user with email and password.

    **Endpoint:** POST `/auth/login`

    **Authentication:** None required

    ---

    ## Request Body (JSON)

    | Field    | Type   | Required | Description                                          |
    |----------|--------|----------|------------------------------------------------------|
    | email    | string | Yes      | The account's email address                          |
    | password | string | Yes      | The account's password (never echoed in the response) |

    ---

    ## Field Validation Rules

    ### email
    - Required, must be a string. No format validation is applied at this endpoint —
        an unrecognised address returns 401 rather than 422.

    ### password
    - Required, must be a string. No length or complexity rules are enforced on login;
        those belong to the endpoint that sets a password.

    ---

    ## Responses

    ### 200 OK
    Credentials accepted. A refresh token row is persisted, the raw refresh token is set
    as an httpOnly cookie scoped to `/auth`, and the access token is returned in the body.

    ```json
    {
        "id": "feab56d6-f7e7-4626-89b4-ac5572d42235",
        "name": "Yassine",
        "email": "yassine@yassinecodes.dev",
        "is_verified": true,
        "is_active": true,
        "auth_provider": "google_password",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```

    ### 401 Unauthorized
    The email is unknown or the password is wrong. Both cases return the identical body
    so the response cannot be used to discover which accounts exist.

    ```json
    {
        "detail": "Invalid credentials."
    }
    ```

    ### 403 Forbidden
    The credentials were correct but the account cannot be used.

    Unverified:
    ```json
    {
        "detail": "Your account is not verified, please verify your email first."
    }
    ```

    Deactivated:
    ```json
    {
        "detail": "Your account has been deactivated."
    }
    ```

    ### 422 Unprocessable Entity
    Schema validation failed before the handler ran.

    ```json
    {
        "detail": [
            {
                "type": "missing",
                "loc": ["body", "password"],
                "msg": "Field required"
            }
        ]
    }
    ```

    ---

    ## Post-Login Flow
    1. The user is looked up by email, with `password_hash` undeferred for this query.
    2. The submitted password is verified before any account-state check, so a wrong
        password and an unknown email are indistinguishable to the caller.
    3. `is_verified` and `is_active` are checked, each with its own 403 message.
    4. An access token (JWT, `ACCESS_TOKEN_EXPIRE_MINUTES`) and an opaque refresh token
        are minted. Only the SHA-256 hash of the refresh token is stored.
    5. The refresh row is committed before the cookie is set, so the client is never
        given a token that does not exist server-side.
    6. The client stores the access token in memory and sends it as `Authorization:
        Bearer <token>`. The refresh cookie is sent automatically to `/auth/refresh`.
    """

    # grab email
    email = login_data.email
    password = login_data.password

    # check if user exist by email
    query = select(UserModel).options(undefer(UserModel.password_hash)).where(UserModel.email == email)
    user = await db.execute(query)
    user_data = user.scalar_one_or_none()

    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # check password before leaking whether the account exists
    if not user_data.verify_password(password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # make sure user is verified and active
    if not user_data.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not verified, please verify your email first.",
        )

    if not user_data.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated.",
        )

    # generate jwt token pair
    access_token = create_access_token(user_data.id)
    refresh_token = create_refresh_token()

    db.add(
        RefreshTokenModel(
            user_id=user_data.id,
            token_hash=refresh_token["stored"],
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await db.commit()

    # refresh in http only cookie
    set_refresh_cookie(response, refresh_token["raw"])

    # access in res model
    res_data = {
        "id": user_data.id,
        "name": user_data.name,
        "email": user_data.email,
        "is_verified": user_data.is_verified,
        "is_active": user_data.is_active,
        "access_token": access_token,
    }

    return res_data
