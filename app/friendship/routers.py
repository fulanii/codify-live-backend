import os
import httpx
from dotenv import load_dotenv

from fastapi import APIRouter, status, HTTPException, Request, Response, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from supabase import AuthApiError

from app.core.supabase_client import supabase
from app.utils.env_helper import env_bool, env_none_or_str
from app.core.dependencies import verify_token

from .schemas import FriendsSearchResponseModel, FriendRequestModel


load_dotenv()
router = APIRouter()
security = HTTPBearer()


@router.get(
    "/search/{username}", response_model=FriendsSearchResponseModel, status_code=200
)
def username_search(username: str, user=Depends(verify_token)):
    """
    Search for users by username (prefix matching).

    This endpoint allows clients to search for other users by providing the
    beginning of a username. It performs a case-insensitive prefix match and
    returns up to 10 results ordered alphabetically.

    **Input**
    - `username`: A search prefix (minimum 3 characters).

    **Returns**
    - `usernames`: A list of matching user objects containing:
        - `id` — The user's unique ID.
        - `username` — The user's username.

    **Errors**
    - `400`: Search term is shorter than 3 characters.
    - `404`: No users matched the search prefix.
    - `500`: Unexpected server or Supabase database error.
    """
    if len(username) < 3:
        raise HTTPException(
            status_code=400, detail="Search term must be at least 3 characters."
        )

    try:
        search_prefix = username.lower() + "%"

        response = (
            supabase.table("profiles")
            .select("username, id")
            .ilike("username", search_prefix)
            .limit(10)
            .order("username")
            .execute()
        )

        if len(response.data) <= 0 or response.count == "None":
            raise HTTPException(status_code=404, detail="No matching usernames.")

        return {"usernames": response.data}

    except AuthApiError as e:
        raise HTTPException(status_code=500, detail="Server/Database error.")


@router.post("/request")
def send_friend_request_using_username(
    data: FriendRequestModel,
    request: Request,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """ """
    # check receiver exists
    receiver_username = data.receiver_username
    receiver_data = (
        supabase.table("profiles")
        .select("id")
        .eq("username", receiver_username)
        .execute()
    )

    if not receiver_data.data:
        raise HTTPException(status_code=404, detail="No matching username")

    receiver_id = receiver_data.data[0]["id"]

    # cant send to self
    token = credentials.credentials
    sender_email = user.get("email")
    sender_data = supabase.auth.get_user(jwt=token)
    sender_id = sender_data.user.id

    if sender_id == receiver_id:
        raise HTTPException(
            status_code=405, detail="Can't send friend request to self."
        )

    # cannot send duplicate request

    # cannot send if already friends

    return data


{
    "iss": "https://qnzweukbxizgiyguxxoz.supabase.co/auth/v1",
    "sub": "101e8883-fc86-40de-9678-e4385902dc2e",
    "aud": "authenticated",
    "exp": 1764041264,
    "iat": 1764037664,
    "email": "yaassineee@x.x",
    "phone": "",
    "app_metadata": {"provider": "email", "providers": ["email"]},
    "user_metadata": {
        "email": "yaassineee@x.x",
        "email_verified": True,
        "phone_verified": False,
        "sub": "101e8883-fc86-40de-9678-e4385902dc2e",
    },
    "role": "authenticated",
    "aal": "aal1",
    "amr": [{"method": "password", "timestamp": 1764037664}],
    "session_id": "c3df2fc9-6e0e-4a70-a1c6-6626167457ff",
    "is_anonymous": False,
}
