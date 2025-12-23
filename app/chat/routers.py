import os
import uuid
import httpx
from dotenv import load_dotenv

from fastapi import APIRouter, status, HTTPException, Request, Response, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from supabase import AuthApiError

from app.core.supabase_client import supabase
from app.core.dependencies import verify_token
from app.utils.get_username import get_username

from .schemas import (
    SendMessageModel,
    SendMessageResponseModel,
    CreateDirectConversationModel,
    CreateDirectConversationResponseModel,
    GetConversationsResponseModel,
    GetMessagesResponseModel,
    GetConversationParticipantsResonseModel,
)


load_dotenv()
router = APIRouter()
security = HTTPBearer()


@router.post(
    "/conversations/direct",
    response_model=CreateDirectConversationResponseModel,
    status_code=200,
)
def get_or_create_direct_conversation(
    data: CreateDirectConversationModel,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Get or create a direct (1-on-1) conversation with another user.

    This endpoint is used when a user initiates a new chat from outside
    an existing conversation (e.g. clicking "Message" on a friend's profile).

    If a direct conversation between the two users already exists, it is returned.
    Otherwise, a new conversation is created and both users are added as members.

    **Input**
    - `receiver_id`: UUID of the friend to message

    **Returns**
    - `conversation_id`: UUID of the direct conversation
    - `is_new`: Whether the conversation was newly created

    **Errors**
    - 401: Unauthorized
    - 403: Users are not friends
    - 500: Database error
    """
    try:
        token = credentials.credentials
        user_data = supabase.auth.get_user(jwt=token)
        sender_id = str(user_data.user.id)
        receiver_id = str(data.receiver_id)

        # Canonical ordering (important for uniqueness)
        u1, u2 = sorted([sender_id, receiver_id])

        # 1. Ensure users are friends
        friendship = (
            supabase.table("friendships")
            .select("id")
            .eq("user1_id", u1)
            .eq("user2_id", u2)
            .limit(1)
            .execute()
        )

        if not friendship.data:
            raise HTTPException(
                status_code=403,
                detail="You can only message users you are friends with.",
            )

        # 2. Check if direct conversation already exists
        direct_convo = (
            supabase.table("direct_conversations")
            .select("conversation_id")
            .eq("user1_id", u1)
            .eq("user2_id", u2)
            .limit(1)
            .execute()
        )

        if direct_convo.data:
            return {
                "conversation_id": direct_convo.data[0]["conversation_id"],
                "is_new": False,
            }

        # 3. Create new conversation
        convo_res = (
            supabase.table("conversations").insert({"is_group": False}).execute()
        )
        conversation_id = convo_res.data[0]["id"]

        # 4. Add members
        supabase.table("conversation_members").insert(
            [
                {"conversation_id": conversation_id, "user_id": sender_id},
                {"conversation_id": conversation_id, "user_id": receiver_id},
            ]
        ).execute()

        # 5. Create direct conversation mapping
        supabase.table("direct_conversations").insert(
            {
                "conversation_id": conversation_id,
                "user1_id": u1,
                "user2_id": u2,
            }
        ).execute()

        return {
            "conversation_id": conversation_id,
            "is_new": True,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to create or fetch conversation.",
        )


@router.post(
    "/messages",
    response_model=SendMessageResponseModel,
    status_code=201,
)
def send_message(
    data: SendMessageModel,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Send a message to an existing conversation.

    This endpoint sends a message to a conversation the user is already
    a member of. Messages are always sent to conversations — never directly
    to users.

    **Input**
    - `conversation_id`: UUID of the conversation
    - `content`: Message text

    **Returns**
    - The newly created message record

    **Errors**
    - 401: Unauthorized
    - 403: User is not a member of the conversation
    - 404: Conversation not found
    - 500: Database error
    """
    try:
        token = credentials.credentials
        user_data = supabase.auth.get_user(jwt=token)
        sender_id = str(user_data.user.id)

        # Ensure users are friends
        # Fetch all members in the conversation
        members_res = (
            supabase.table("conversation_members")
            .select("user_id")
            .eq("conversation_id", str(data.conversation_id))
            .execute()
        )

        user_ids = [row["user_id"] for row in members_res.data]

        other_user_id = next(uid for uid in user_ids if uid != sender_id)

        # Canonical ordering
        u1, u2 = sorted([sender_id, other_user_id])

        # Check friendship still exists
        friendship = (
            supabase.table("friendships")
            .select("id")
            .eq("user1_id", u1)
            .eq("user2_id", u2)
            .limit(1)
            .execute()
        )

        if not friendship.data:
            raise HTTPException(
                status_code=403,
                detail="You are no longer friends with this user.",
            )

        # 2. Ensure user is a member of the conversation
        membership = (
            supabase.table("conversation_members")
            .select("id")
            .eq("conversation_id", str(data.conversation_id))
            .eq("user_id", sender_id)
            .limit(1)
            .execute()
        )

        if not membership.data:
            raise HTTPException(
                status_code=403,
                detail="You are not a participant in this conversation.",
            )

        # 3. Insert message
        msg_res = (
            supabase.table("messages")
            .insert(
                {
                    "conversation_id": str(data.conversation_id),
                    "sender_id": sender_id,
                    "content": data.content,
                }
            )
            .execute()
        )

        return {"response_data": msg_res.data}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to send message.",
        )


@router.get(
    "/conversations",
    response_model=GetConversationsResponseModel,
    status_code=200,
)
def get_conversations(
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Retrieve all conversations for the authenticated user.

    This endpoint returns every conversation the current user is a member of.
    Membership is determined via the `conversation_members` table, which acts
    as the authorization layer for conversations.

    The result is typically used to populate the chat sidebar or inbox view.

    **Returns**
    - `conversations`: List of conversation objects
        - `id`: Conversation ID
        - `is_group`: Whether the conversation is a group chat
        - `created_at`: Conversation creation timestamp

    **Errors**
    - 401: Invalid or expired JWT
    - 500: Database or unexpected server error
    """
    try:
        token = credentials.credentials
        user_data = supabase.auth.get_user(jwt=token)

        if not user_data or not user_data.user:
            raise HTTPException(status_code=401, detail="Invalid authentication")

        user_id = user_data.user.id

        conversations = (
            supabase.table("conversation_members")
            .select(
                """
                conversation_id,
                conversations (
                    id,
                    is_group,
                    created_at
                )
                """
            )
            .eq("user_id", str(user_id))
            .execute()
        )

        return {
            "conversations": [
                row["conversations"]
                for row in conversations.data or []
                if row.get("conversations")
            ]
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")


@router.get(
    "/messages/{conversation_id}",
    response_model=GetMessagesResponseModel,
    status_code=200,
)
def get_messages(
    conversation_id: str,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Retrieve all messages for a conversation.

    Returns the full message history for a given conversation, ordered from
    oldest to newest. The authenticated user must be a member of the
    conversation in order to access its messages.

    **Path Parameters**
    - `conversation_id`: UUID of the conversation

    **Returns**
    - `messages`: List of message objects
        - `id`: Message UUID
        - `sender_id`: User ID of the sender
        - `content`: Message text
        - `created_at`: Timestamp when the message was sent

    **Errors**
    - 401: Invalid or expired authentication token
    - 403: User is not a member of the conversation
    - 404: Conversation does not exist
    - 500: Database or unexpected server error
    """
    try:
        token = credentials.credentials
        user_data = supabase.auth.get_user(jwt=token)

        if not user_data or not user_data.user:
            raise HTTPException(status_code=401, detail="Invalid authentication")

        user_id = user_data.user.id

        # Verify conversation exists
        conversation_check = (
            supabase.table("conversations")
            .select("id")
            .eq("id", conversation_id)
            .limit(1)
            .execute()
        )

        if not conversation_check.data:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Verify user is a member of the conversation
        membership_check = (
            supabase.table("conversation_members")
            .select("id")
            .eq("conversation_id", conversation_id)
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )

        if not membership_check.data:
            raise HTTPException(
                status_code=403, detail="You are not a member of this conversation"
            )

        messages = (
            supabase.table("messages")
            .select("id, sender_id, content, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )

        final_data = []

        for row in messages.data:
            updated_row = {
                **dict(row),
                "sender_username": get_username(row["sender_id"]),
            }
            final_data.append(updated_row)

        return {"messages": final_data}

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")


@router.get(
    "/conversation/participants/{conversation_id}",
    response_model=GetConversationParticipantsResonseModel,
    status_code=200,
)
def get_conversation_participant_info(
    conversation_id: str,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Retrieves the username and friendship status of the other participant in a direct conversation.

    Args:
        conversation_id (str): The unique identifier for the direct conversation.
        user (dict): Validated user data from the verify_token dependency.
        credentials (HTTPAuthorizationCredentials): Bearer token for authentication.

    Returns:
        {'participant_username': 'actual_username', 'is_friend': bool}

    """
    try:
        token = credentials.credentials
        user_data = supabase.auth.get_user(jwt=token)
        user_id = str(user_data.user.id)

        participansts = (
            supabase.table("direct_conversations")
            .select("user1_id, user2_id")
            .eq("conversation_id", conversation_id)
            .limit(1)
            .execute()
        )

        data = participansts.data[0]

        user1_id = data.get("user1_id")
        user2_id = data.get("user2_id")

        # Check if the current user is even in this conversation
        if user_id not in [user1_id, user2_id]:
            raise HTTPException(
                status_code=403, detail="You are not a member of this conversation"
            )

        # Canonical ordering
        u1, u2 = sorted([user1_id, user2_id])

        # check friendship.
        is_friend = True
        friendship = (
            supabase.table("friendships")
            .select("id")
            .eq("user1_id", u1)
            .eq("user2_id", u2)
            .limit(1)
            .execute()
        )

        if not friendship.data:
            is_friend = False

        other_user_id = user2_id if user_id == user1_id else user1_id

        username = get_username(other_user_id)

        if not username:
            raise HTTPException(
                status_code=404, detail="Participant username could not be found."
            )

        return {"participant_username": username, "is_friend": is_friend}

    except HTTPException as http_ex:
        raise http_ex

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )
