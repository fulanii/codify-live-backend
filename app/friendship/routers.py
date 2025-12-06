import os
import uuid
import httpx
from dotenv import load_dotenv

from fastapi import APIRouter, status, HTTPException, Request, Response, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from supabase import AuthApiError

from app.core.supabase_client import supabase
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


@router.post("/request", response_model=FriendRequestResponseModel, status_code=201)
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
        raise HTTPException(500, detail="Database error while looking up receiver.")

    if not receiver_query.data:
        raise HTTPException(404, detail="No matching username.")

    receiver_id = receiver_query.data[0]["id"]

    # Get sender from token
    try:
        token = credentials.credentials
        sender_data = supabase.auth.get_user(jwt=token)
        sender_id = sender_data.user.id
    except AuthApiError:
        raise HTTPException(401, detail="Invalid or expired token.")
    except Exception:
        raise HTTPException(500, detail="Unexpected authentication error.")

    # Prevent sending to self
    if sender_id == receiver_id:
        raise HTTPException(405, detail="Cannot send friend request to yourself.")

    # Prevent sending if friend request already exist
    try:
        existing_request = (
            supabase.table("friendships_requests")
            .select("sender_id, receiver_id")
            .eq("sender_id", f"{sender_id}")
            .eq("receiver_id", f"{receiver_id}")
            .execute()
        )
    except Exception as e:
        raise HTTPException(500, detail="Database error while checking friendship.")

    if existing_request.data:
        raise HTTPException(
            409,
            detail="Friend request already sent (or already pending from the other user).",
        )

    # Prevent sending if already friends
    try:
        check_friendships = (
            supabase.table("friendships")
            .select("id")
            .or_(
                f"user1_id.eq.{sender_id},user2_id.eq.{receiver_id},"
                f"user1_id.eq.{receiver_id},user2_id.eq.{sender_id}"
            )
            .limit(1)
            .execute()
        )
    except Exception as e:
        raise HTTPException(500, detail="Database error while checking friendship.")

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
        raise HTTPException(500, detail=f"Database error while creating request: {e}")

    return {
        "message": "Friend request sent.",
        "request": created_request.data[0],
    }


@router.post(
    "/request/accept", response_model=AcceptFriendRequestResponseModel, status_code=201
)
def accept_friend_request(
    data: AcceptFriendRequestModel,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Accept a friend request between two users.

    This endpoint allows an authenticated user (`receiver`) to accept a
    pending friend request sent by another user (`sender`). Once accepted:

    - The `friendships_requests` row is updated to `"Accepted"`.
    - A new friendship row is inserted into the `friendships` table
    using (`user1_id`, `user2_id`) ordering logic.

    The system checks for the existence of a matching friend request in
    both possible sender/receiver directions to ensure correct behavior.

    **Input**
    - `sender_id`: The ID of the user who originally sent the request.

    **Behavior**
    1. Validate that a pending friend request exists between the two users.
    2. Update the friend request status to `"Accepted"`.
    3. Insert a new friendship record.
    4. Prevents accepting a nonexistent or already-handled request.

    **Returns**
    - `200 OK`: Confirmation that the friend request was accepted.
    - Newly created friendship record.

    **Errors**
    - `404`: No such friend request exists.
    - `409`: Request already accepted, declined, cancelled, or invalid.
    - `500`: Unexpected database/server error.

    **Notes**
    - Only the receiver of the request can accept it.
    - Reverse sender/receiver orderings are checked to avoid duplication.
    """

    token = credentials.credentials
    receiver_data = supabase.auth.get_user(jwt=token)

    sender_id = data.sender_id
    receiver_id = receiver_data.user.id

    try:
        # check to see if friendship request exist between both sender and receiver
        check_friendships_request = (
            supabase.table("friendships_requests")
            .select("sender_id, receiver_id")
            .or_(
                f"sender_id.eq.{sender_id},receiver_id.eq.{receiver_id},"
                f"sender_id.eq.{receiver_id},receiver_id.eq.{sender_id}"
            )
            .execute()
        )
        if not check_friendships_request.data:
            raise HTTPException(
                409,
                detail="Friend request doesn't exist.",
            )
    except HTTPException:
        raise HTTPException(
            409,
            detail="Friend request doesn't exist.",
        )

    try:
        # if yess update friendships_requests status as accepted (delete 'Declined', 'Cancelled' later w cron job)
        update_result = (
            supabase.table("friendships_requests")
            .delete()
            .eq("sender_id", sender_id)
            .eq("receiver_id", receiver_id)
            .execute()
        )

        u1, u2 = sorted([str(sender_id), str(receiver_id)])

        # create new friendship role
        insert_new_friendship = (
            supabase.table("friendships")
            .insert(
                {
                    "user1_id": u1,
                    "user2_id": u2,
                }
            )
            .execute()
        )

        returned_data = insert_new_friendship.data[0]

        return {
            "friendship_accept": True,
            "details": {
                "friendship_id": returned_data["id"],
                "sender_id": returned_data["user1_id"],
                "receiver_id": returned_data["user2_id"],
                "created_at": returned_data["created_at"],
            },
        }
    except Exception:
        raise HTTPException(500, detail="Database error while updating friendship.")


# Decline Friend Request (only receiver can)
# Only Receiver can decline
@router.delete(
    "/request/decline/{sender_id}",
    response_model=DeclineFriendshipRequestResponseModel,
    status_code=200,
)
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

    token = credentials.credentials
    receiver_data = supabase.auth.get_user(jwt=token)
    receiver_id = receiver_data.user.id

    # Query only pending requests
    request_query = (
        supabase.table("friendships_requests")
        .select("sender_id, receiver_id, status")
        .eq("sender_id", sender_id)
        .eq("receiver_id", receiver_id)
        .eq("status", "Pending")
        .execute()
    )

    if not request_query.data:
        raise HTTPException(status_code=404, detail="No pending friend request found.")

    (
        supabase.table("friendships_requests")
        .delete()
        .eq("sender_id", sender_id)
        .eq("receiver_id", receiver_id)
        .eq("status", "Pending")
        .execute()
    )

    return {"request_declined": True}


# Cancel Friend Request (Only the sender can cancel.)print()
@router.delete(
    "/request/cancel/{receiver_id}",
    response_model=CancelFriendshipRequestResponseModel,
    status_code=200,
)
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


@router.delete(
    "/remove/{other_user_id}",
    response_model=RemoveFriendResponseModel,
    status_code=200,
)
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


# TODO: Implement Block