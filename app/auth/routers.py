import os
import httpx
import logging
from dotenv import load_dotenv

from fastapi.responses import JSONResponse
from fastapi import APIRouter, status, HTTPException, Request, Response, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from supabase import AuthApiError

from app.core.supabase_client import supabase
from app.utils.env_helper import env_bool, env_none_or_str
from app.core.dependencies import verify_token
from .schemas import (
    UserRegistrationModel,
    UserRegistrationResponseModel,
    UserLoginModel,
    UserLoginResponseModel,
    AccessTokenResponseModel,
    MeResponseModel,
)


load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


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
        logger.error(f"supabase_error={error}")
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

    logger.info(f"user_login_success email={data.email}, username={data.username}")

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

            logger.info(f"user_login_success email={user_data.email}")

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
        print(e)
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


@router.get("/me", response_model=MeResponseModel, status_code=200)
def get_me(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user=Depends(verify_token),
):
    """
    Get full authenticated user profile including auth info, profile,
    friendships, and friendship requests.

    This endpoint returns everything related to the logged-in user:

    **Returns**
    - `auth`: user's id & email (from `auth.users`)
    - `profile`: username & created_at (from `profiles`)
    - `friends`: list of accepted friends with usernames
    - `incoming_requests`: users who sent YOU a request
    - `outgoing_requests`: users YOU sent a request to

    **Errors**
    - `401`: Invalid or expired token
    - `404`: Profile not found
    - `500`: Database or server error
    """
    try:
        # --- 1. Get authenticated user from Supabase ---
        token = credentials.credentials
        user_data = supabase.auth.get_user(jwt=token)

        if not user_data or not user_data.user:
            raise HTTPException(401, "Invalid authentication token.")

        user_id = user_data.user.id
        user_email = user_data.user.email

        # --- 2. Fetch profile ---
        profile_query = (
            supabase.table("profiles")
            .select("username, created_at")
            .eq("id", user_id)
            .single()
            .execute()
        )

        if not profile_query.data:
            raise HTTPException(404, "Profile not found.")

        profile = profile_query.data

        # --- 3. Fetch friendships ---
        # Need to find all rows where user1_id = me OR user2_id = me
        friends_query = (
            supabase.table("friendships")
            .select("user1_id, user2_id, created_at")
            .or_(f"user1_id.eq.{user_id},user2_id.eq.{user_id}")
            .execute()
        )

        friends_rows = friends_query.data or []

        # Resolve friend's ID (the "other" user)
        friend_ids = [
            row["user2_id"] if row["user1_id"] == user_id else row["user1_id"]
            for row in friends_rows
        ]

        # Fetch usernames of all friends
        friends_usernames = []
        if friend_ids:
            friends_usernames_result = (
                supabase.table("profiles")
                .select("id, username")
                .in_("id", friend_ids)
                .execute()
            )
            friends_usernames = friends_usernames_result.data

        # Attach username to friend record
        friends_output = []
        for row in friends_rows:
            friend_id = (
                row["user2_id"] if row["user1_id"] == user_id else row["user1_id"]
            )

            username = next(
                (u["username"] for u in friends_usernames if u["id"] == friend_id),
                None,
            )

            friends_output.append(
                {
                    "friend_id": friend_id,
                    "username": username,
                    "created_at": row["created_at"],
                }
            )

        # --- 4. Incoming friend requests (others → me) ---
        incoming_requests = (
            supabase.table("friendships_requests")
            .select("id, sender_id, status, created_at")
            .eq("receiver_id", user_id)
            .eq("status", "Pending")
            .execute()
        ).data or []

        # Resolve usernames for incoming senders
        incoming_sender_ids = [r["sender_id"] for r in incoming_requests]
        incoming_usernames = []
        if incoming_sender_ids:
            incoming_usernames = (
                supabase.table("profiles")
                .select("id, username")
                .in_("id", incoming_sender_ids)
                .execute()
            ).data

        # Attach username
        incoming_requests_output = []
        for r in incoming_requests:
            username = next(
                (
                    u["username"]
                    for u in incoming_usernames
                    if u["id"] == r["sender_id"]
                ),
                None,
            )

            incoming_requests_output.append(
                {
                    "id": r["id"],
                    "sender_id": r["sender_id"],
                    "username": username,
                    "status": r["status"],
                    "created_at": r["created_at"],
                }
            )

        # --- 5. Outgoing friend requests (me → others) ---
        outgoing_requests = (
            supabase.table("friendships_requests")
            .select("id, receiver_id, status, created_at")
            .eq("sender_id", user_id)
            .eq("status", "Pending")
            .execute()
        ).data or []

        # Resolve usernames
        outgoing_receiver_ids = [r["receiver_id"] for r in outgoing_requests]
        outgoing_usernames = []
        if outgoing_receiver_ids:
            outgoing_usernames = (
                supabase.table("profiles")
                .select("id, username")
                .in_("id", outgoing_receiver_ids)
                .execute()
            ).data

        # Attach username
        outgoing_requests_output = []
        for r in outgoing_requests:
            username = next(
                (
                    u["username"]
                    for u in outgoing_usernames
                    if u["id"] == r["receiver_id"]
                ),
                None,
            )

            outgoing_requests_output.append(
                {
                    "id": r["id"],
                    "receiver_id": r["receiver_id"],
                    "username": username,
                    "status": r["status"],
                    "created_at": r["created_at"],
                }
            )

        # --- FINAL RESPONSE ---
        return {
            "auth": {
                "id": user_id,
                "email": user_email,
            },
            "profile": profile,
            "friends": friends_output,
            "incoming_requests": incoming_requests_output,
            "outgoing_requests": outgoing_requests_output,
        }

    except Exception as e:
        print("Error in /auth/me:", e)
        raise HTTPException(500, detail=f"Internal server error: {e}")


@router.post("/logout")
def logout():
    """
    Logs out the user by clearing the refresh_token cookie that was used
    during authentication. Supabase itself cannot invalidate JWTs early,
    so logout consists of deleting the refresh token stored in cookies.
    """

    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    response = JSONResponse({"logged_out": True})

    # Delete your custom refresh token cookie
    response.delete_cookie(
        key="refresh_token",
        path="/auth/access",  # must match set_cookie()
        domain=env_none_or_str("COOKIE_DOMAIN", None),
    )

    return response


# TODO: Implement Password reset


# TODO: Implement Email change
