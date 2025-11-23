import os
import httpx
from dotenv import load_dotenv

from fastapi import APIRouter, status, HTTPException, Request, Response

from supabase import AuthApiError

from app.core.supabase_client import supabase
from app.utils.utils import env_bool, env_none_or_str
from app.models.auth_models import (
    UserRegistrationModel,
    UserRegistrationResponseModel,
    UserLoginModel,
    UserLoginResponseModel,
    AccessTokenResponseModel,
)


load_dotenv()
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRegistrationResponseModel, status_code=201)
def register_user(data: UserRegistrationModel):
    """
    Register a new user.

    This endpoint creates a Supabase Auth user and a corresponding profile record.
    It accepts an email, username, and password, performs basic validation, and
    returns the new user's ID and email upon successful registration.

    **Input Fields**
    - **email**: A valid user email. Must not already exist in Supabase Auth.
    - **username**: 3–8 characters, containing only letters, numbers, underscores, or dots.
    - **password**: Minimum 8 characters. Must include:
        - at least one lowercase letter
        - at least one uppercase letter
        - at least one number
        - at least one special character
          (validated using: `^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*()_+={}\[\]|\\;:'\",.<>?/~`]).{8,}$`)

    **Returns**
    - User ID
    - Email
    - Username

    **Errors**
    - 400: Invalid input or failed to create user
    - 409: Email or Username already registered
    - 500: Unexpected Supabase or server error
    """

    # Check if username already exists
    username_check = (
        supabase.table("profiles").select("id").eq("username", data.username).execute()
    )

    if username_check.data:
        raise HTTPException(status_code=409, detail="Username already taken.")

    # Create Supabase Auth user
    try:
        res = supabase.auth.sign_up(
            {
                "email": data.email,
                "password": data.password.get_secret_value(),
            }
        )
    except AuthApiError as error:
        raise HTTPException(status_code=409, detail=str(error))

    if not res.user:
        raise HTTPException(status_code=400, detail="Failed to create user")

    user_id = res.user.id

    supabase.table("profiles").insert(
        {
            "id": user_id,
            "username": data.username,
        }
    ).execute()

    return {
        "id": user_id,
        "email": res.user.email,
        "username": data.username,
    }


@router.post("/login", response_model=UserLoginResponseModel, status_code=200)
def login_user(user_data: UserLoginModel, response: Response):
    """
    Authenticate a user with email and password.

    This endpoint checks credentials against Supabase Auth and returns a new
    access token along with basic user information. A refresh token may also
    be set in an HttpOnly cookie.

    **Input Fields**
    - **email**: The user's email address.
    - **password**: The user's password.

    **Returns**
    - `access_token`: A short-lived JWT used for authorized API requests.
    - `user_id`: The authenticated user's ID.
    - `email`: The authenticated user's email.

    **Errors**
    - 401: Invalid email or password
    - 500: Supabase or internal server error
    """

    try:
        res = supabase.auth.sign_in_with_password(
            {
                "email": user_data.email,
                "password": user_data.password.get_secret_value(),
            }
        )

        if res.session:
            response.set_cookie(
                key="refresh_token",
                value=res.session.refresh_token,
                httponly=env_bool("HTTPONLY", default=True),
                secure=env_bool("SECURE", default=False),
                samesite=os.getenv("SAMESITE", "Lax"),
                domain=env_none_or_str("COOKIE_DOMAIN", None),
                max_age=60 * 60 * 24 * 7,  # 7 days
                path="/auth/access",
            )
            return {
                "access_token": res.session.access_token,
                "expires_in": res.session.expires_in,
                "user_id": res.user.id,
                "email": res.user.email,
            }

        raise HTTPException(
            status_code=500,
            detail="Supabase authentication returned an unexpected response.",
        )

    except AuthApiError as error:
        raise HTTPException(status_code=401, detail=error.message)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail="An internal server error occurred during login."
        )


@router.get("/access", response_model=AccessTokenResponseModel, status_code=200)
def get_new_access(request: Request, response: Response):
    """
    Issue a new access token using the refresh token stored in an HttpOnly cookie.

    This endpoint reads the `refresh_token` from the incoming request's cookies
    and exchanges it for a fresh access token through Supabase's session refresh
    mechanism. If rotation is enabled, a new refresh token will be returned and
    the cookie will be updated automatically.

    **Input**
    - No JSON body.
    - Reads `refresh_token` from an HttpOnly cookie.

    **Returns**
    - A new `access_token`
    - Token type and expiration info
    - The user's ID
    - (Optional) Updated refresh token in `refresh_token` cookie

    **Errors**
    - 401: Missing, expired, revoked, or invalid refresh token
    - 500: Unexpected internal server error
    """

    COOKIE_NAME = "refresh_token"

    refresh_token = request.cookies.get(COOKIE_NAME)

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided.",
        )

    try:
        session = supabase.auth.refresh_session(refresh_token)

        new_refresh_token = session.session.refresh_token
        new_access_token = session.session.access_token

        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=env_bool("HTTPONLY", default=True),
            secure=env_bool("SECURE", default=False),
            samesite=os.getenv("SAMESITE", "Lax"),
            domain=env_none_or_str("COOKIE_DOMAIN", None),
            max_age=60 * 60 * 24 * 7,  # 7 days
            path="/auth/access",
        )
        return {"access_token": new_access_token}

    except Exception as e:
        response.delete_cookie(
            key=COOKIE_NAME,
            domain=os.getenv("COOKIE_DOMAIN"),
            path="/auth/access",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalid or expired. Please log in again.",
        )


# TODO: Implement Password reset


# TODO: Implement Email change
