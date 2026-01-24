import os
import uuid
import httpx
import logging
from dotenv import load_dotenv

from fastapi import APIRouter, status, HTTPException, Request, Response, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from supabase import AuthApiError

from app.core.supabase_client import supabase, supabase_admin
from app.utils.env_helper import env_bool, env_none_or_str
from app.core.dependencies import verify_token

from .schemas import (
    FriendsSearchResponseModel,
    FriendRequestModel,
    FriendRequestResponseModel,
    FriendRequestResponseModel,
    AcceptFriendRequestModel,
    AcceptFriendRequestResponseModel,
    DeclineFriendshipRequestResponseModel,
    CancelFriendshipRequestResponseModel,
    RemoveFriendResponseModel,
)


load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

# TODO: Add logging


@router.get(
    "/search/{username}", response_model=FriendsSearchResponseModel, status_code=200
)
def username_search(username: str, user=Depends(verify_token)):  # ✅
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


@router.post(
    "/request", response_model=FriendRequestResponseModel, status_code=201
)  # ✅
def create_friend_request_using_username(
    data: FriendRequestModel,
    request: Request,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Send a friend request to another user using their username.

    This endpoint allows an authenticated user to initiate a friend request
    toward another registered user. A series of validation steps ensure
    that requests are not duplicated, users cannot send requests to
    themselves, and that existing friendships or pending requests
    are respected.

    **Input**
    - `receiver_username`: A valid username belonging to another user.

    **Process**
    1. Validate that the target user exists.
    2. Identify the requester using the bearer token.
    3. Prevent self–friend-requests.
    4. Prevent duplicate pending requests.
    5. Prevent sending requests to users who are already friends.
    6. Create a new `Pending` friendship request.

    **Returns**
    - `{ "message": "Friend request sent.", "request": {...} }`

    **Errors**
    - `404`: No user found with the provided username.
    - `405`: Attempt to send a friend request to yourself.
    - `409`: Duplicate request or already friends.
    - `401`: Invalid or expired token.
    - `500`: Database or unexpected server error.
    """
    token = credentials.credentials
    sender_data = supabase.auth.get_user(jwt=token)
    sender_id = sender_data.user.id
    receiver_username = data.receiver_username

    # Receiver exists
    try:
        receiver_query = (
            supabase.table("profiles")
            .select("id, username")
            .eq("username", receiver_username)
            .execute()
        )
    except Exception:
        raise HTTPException(500, detail="Server error.")

    if not receiver_query.data:
        raise HTTPException(404, detail="No matching username.")

    receiver_id = receiver_query.data[0]["id"]

    # Prevent sending to self
    if sender_id == receiver_id:
        raise HTTPException(403, detail="Cannot send friend request to yourself.")

    # Prevent sending if friend request already exist
    try:
        existing_request = (
            supabase.table("friendships_requests")
            .select("sender_id, receiver_id")
            .or_(
                f"and(sender_id.eq.{sender_id},receiver_id.eq.{receiver_id}),"  # Scenario A
                f"and(sender_id.eq.{receiver_id},receiver_id.eq.{sender_id})"  # Scenario B
            )
            # .or_(
            #     f"sender_id.eq.{sender_id},receiver_id.eq.{receiver_id},"
            #     f"sender_id.eq.{receiver_id},receiver_id.eq.{sender_id}"
            # )
            # .eq("receiver_id", receiver_id)
            # .eq("sender_id", sender_id)
            .limit(1)
            .execute()
        )
    except Exception as e:
        raise HTTPException(500, detail="Server error.")
    print(existing_request)
    if existing_request.data:
        raise HTTPException(
            409,
            detail="Friend request already sent (or already pending from the other user).",
        )

    # Prevent sending if already friends
    try:
        u1, u2 = sorted([sender_id, receiver_id])

        check_friendships = (
            supabase.table("friendships")
            .select("user1_id, user2_id")
            .eq("user1_id", u1)
            .eq("user2_id", u2)
            .limit(1)
            .execute()
        )
    except Exception as e:
        raise HTTPException(500, detail="Server error.")

    if check_friendships.data:
        raise HTTPException(409, detail="Already friends with this user.")

    # Create request
    try:
        created_request = (
            supabase.table("friendships_requests")
            .insert(
                {
                    "sender_id": sender_id,
                    "receiver_id": receiver_id,
                    "status": "Pending",
                }
            )
            .execute()
        )
    except Exception as e:
        raise HTTPException(500, detail=f"Server error.")

    return {
        "message": "Friend request sent.",
        "request": created_request.data[0],
    }


# Accept Friend Request (only receiver can)
@router.post(
    "/request/accept", status_code=201, response_model=AcceptFriendRequestResponseModel
)  # ✅✅
def accept_friend_request(
    data: AcceptFriendRequestModel,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Accept a pending friend request between two users.
    Only receiver can accept friend request

    The authenticated user becomes the `receiver`. This endpoint:
    - verifies a pending friend request exists from sender to receiver
    - deletes the request row
    - creates a friendship row with canonical ordering (user1 < user2)

    Errors:
    - 404: no pending request exists
    - 500: database failure
    """

    token = credentials.credentials
    sender_id = str(data.sender_id)
    receiver_data = supabase.auth.get_user(jwt=token)
    receiver_id = str(receiver_data.user.id)

    try:
        # 1. Look for pending request
        check_request = (
            supabase.table("friendships_requests")
            .select("id, sender_id, receiver_id, status")
            .eq("receiver_id", receiver_id)
            .eq("sender_id", sender_id)
            .eq("status", "Pending")
            .limit(1)
            .execute()
        )

        if not check_request.data:
            logger.info(f"friend_request_doesnt_exist")
            raise HTTPException(
                status_code=404, detail="Friend request does not exist."
            )

        # only receiver can accept
        if receiver_id != check_request.data[0]["receiver_id"]:
            logger.info(f"user_cant_accept_friend_request")
            raise HTTPException(403, detail="You can't accept this friend request.")

        # 3. delete request
        supabase_admin.table("friendships_requests").delete().eq(
            "id", check_request.data[0]["id"]
        ).execute()

        # 4. canonical ordering
        u1, u2 = sorted([sender_id, receiver_id])

        friendship = (
            supabase_admin.table("friendships")
            .insert({"user1_id": u1, "user2_id": u2})
            .execute()
        )

        row = friendship.data[0]

        return {
            "friendship_accept": True,
            "details": {
                "friendship_id": row["id"],
                "user1_id": row["user1_id"],
                "user2_id": row["user2_id"],
                "created_at": row["created_at"],
            },
        }

    except Exception as e:
        logger.error(f"error_asccepting_friend error={e}")
        raise HTTPException(
            status_code=500,
            detail="Server error.",
        )


# Decline Friend Request (only receiver can)
@router.delete(
    "/request/decline/{sender_id}",
    response_model=DeclineFriendshipRequestResponseModel,
    status_code=200,
)  # ✅
def decline_friend_request(
    sender_id: str,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Decline a pending friendship request sent by the specified user.

    Args:
        sender_id (str):
            The ID of the user who originally sent the friend request.
        user:
            The authenticated user dependency (from verify_token).
        credentials (HTTPAuthorizationCredentials):
            Authorization header containing the user's JWT.

    Returns:
        DeclineFriendshipRequestResponseModel:
            A response indicating whether the request was successfully declined.

    Raises:
        HTTPException (404):
            If no pending friend request exists from the sender to the authenticated user.
        HTTPException (500):
            If a database or server error occurs.

    Summary:
        This endpoint allows the authenticated user (receiver) to decline a friend
        request sent by `sender_id`. It validates the request, checks that it is
        still pending, updates its status to "Declined", and returns a simple
        success response.
    """

    try:

        token = credentials.credentials
        receiver_data = supabase.auth.get_user(jwt=token)
        receiver_id = receiver_data.user.id

        # Query only pending requests for these users
        request_query = (
            supabase.table("friendships_requests")
            .select("sender_id, receiver_id, status")
            .eq("sender_id", sender_id)
            .eq("receiver_id", receiver_id)
            .eq("status", "Pending")
            .limit(1)
            .execute()
        )

        if not request_query.data:
            logger.error(f"no_pending_friendship")
            raise HTTPException(
                status_code=404, detail="No pending friend request found."
            )

        # only receiver can decline
        if receiver_id != request_query.data[0]["receiver_id"]:
            logger.error(f"friend_cant_decline_error error={e}")
            raise HTTPException(403, detail="You can't decline this friend request.")

        (
            supabase.table("friendships_requests")
            .delete()
            .eq("sender_id", sender_id)
            .eq("receiver_id", receiver_id)
            .eq("status", "Pending")
            .execute()
        )

        return {"request_declined": True}

    except Exception as e:
        logger.error(f"friend_decline_error error={e}")
        raise HTTPException(
            status_code=500,
            detail="Server error.",
        )


# Cancel Friend Request (Only the sender can cancel.)
@router.delete(
    "/request/cancel/{receiver_id}",
    response_model=CancelFriendshipRequestResponseModel,
    status_code=200,
)  # ✅
def cancel_friend_request(
    receiver_id: str,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Cancel a pending friendship request previously sent by the authenticated user.

    Args:
        receiver_id (str):
            The ID of the user who received the original friend request.
        user:
            The authenticated user dependency (from verify_token).
        credentials (HTTPAuthorizationCredentials):
            Authorization header containing the user's JWT.

    Returns:
        CancelFriendshipRequestResponseModel:
            A response indicating whether the friend request was successfully canceled.

    Raises:
        HTTPException (404):
            If no pending friend request exists between the sender and receiver.
        HTTPException (500):
            If a database or server error occurs.

    Summary:
        This endpoint allows the sender to cancel a friend request that is still in
        the 'Pending' state. Only the original sender can perform this action.
    """

    try:
        token = credentials.credentials
        sender_data = supabase.auth.get_user(jwt=token)
        sender_id = sender_data.user.id

        # Check if the pending request exists
        request_query = (
            supabase.table("friendships_requests")
            .select("sender_id, receiver_id, status")
            .eq("sender_id", sender_id)
            .eq("receiver_id", receiver_id)
            .eq("status", "Pending")
            .execute()
        )

        if not request_query.data:
            raise HTTPException(
                status_code=404, detail="No pending friend request to cancel."
            )

        # only receiver can decline
        if sender_id != request_query.data[0]["sender_id"]:
            raise HTTPException(403, detail="You can't decline this friend request.")

        # Delete the pending request
        (
            supabase.table("friendships_requests")
            .delete()
            .eq("sender_id", sender_id)
            .eq("receiver_id", receiver_id)
            .eq("status", "Pending")
            .execute()
        )

        return {"request_canceled": True}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Server error.",
        )


@router.delete(
    "/remove/{other_user_id}",
    response_model=RemoveFriendResponseModel,
    status_code=200,
)  # ✅
def remove_friend(
    other_user_id: str,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Remove an existing friendship between the authenticated user and another user.

    Args:
        other_user_id (str):
            The ID of the user to remove from the authenticated user's friend list.
        user:
            Authenticated user dependency (verify_token).
        credentials (HTTPAuthorizationCredentials):
            Authorization header containing the JWT token.

    Returns:
        RemoveFriendResponseModel:
            Indicates whether the friendship was removed successfully.

    Raises:
        HTTPException (404):
            If no friendship exists between the users.
        HTTPException (500):
            If a database error occurs.
    """
    try:
        # Extract current authenticated user ID
        token = credentials.credentials
        auth_user = supabase.auth.get_user(jwt=token)
        current_user_id = auth_user.user.id

        # Canonical ordering (must match SQL CHECK constraint)
        u1, u2 = sorted([current_user_id, other_user_id])

        # Check if friendship exists
        friendship_query = (
            supabase.table("friendships")
            .select("id")
            .eq("user1_id", u1)
            .eq("user2_id", u2)
            .execute()
        )

        if not friendship_query.data:
            raise HTTPException(status_code=404, detail="Friendship does not exist.")

        # Delete friendship
        delete_result = (
            supabase.table("friendships")
            .delete()
            .eq("user1_id", u1)
            .eq("user2_id", u2)
            .execute()
        )

        return {"friend_removed": True}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Server error.",
        )


# TODO: Implement Block
