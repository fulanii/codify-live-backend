import os
import uuid
import httpx
from dotenv import load_dotenv

from fastapi import APIRouter, status, HTTPException, Request, Response, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from supabase import AuthApiError

from app.core.supabase_client import supabase
from app.core.dependencies import verify_token

from .schemas import SendMessageModel, SendMessageResponseModel


load_dotenv()
router = APIRouter()
security = HTTPBearer()


@router.post("/send", response_model=SendMessageResponseModel, status_code=201)
def send_message(
    data: SendMessageModel,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Send a message to a conversation.

    This endpoint allows an authenticated user to send a message to an existing
    conversation. The sender is derived from the JWT access token to prevent
    spoofing. Upon insertion, Supabase Realtime will automatically broadcast
    the new message to all subscribed clients.

    **Input**
    - `conversation_id`: ID of the conversation
    - `content`: Message text

    **Returns**
    - The newly created message record

    **Errors**
    - 401: Unauthorized or invalid token
    - 403: User is not a participant in the conversation
    - 500: Database error
    """
    token = credentials.credentials
    user_data = supabase.auth.get_user(jwt=token)
    sender_id = user_data.user.id

    # Optional but recommended: ensure user belongs to conversation
    membership_check = (
        supabase.table("conversation_members")
        .select("id")
        .eq("conversation_id", str(data.conversation_id))
        .eq("user_id", str(sender_id))
        .limit(1)
        .execute()
    )

    if not membership_check.data:
        raise HTTPException(
            status_code=403, detail="Not a member of this conversation."
        )

    res = (
        supabase.table("messages")
        .insert(
            {
                "conversation_id": str(data.conversation_id),
                "sender_id": str(sender_id),
                "content": data.content,
            }
        )
        .execute()
    )

    return {"message": res.data[0]}


@router.get(
    "/messages/{conversation_id}",
    # response_model=GetMessagesResponseModel,
    status_code=200,
)
def get_messages(
    conversation_id: str,
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Fetch messages for a conversation.

    Returns the message history for a given conversation. The requesting user
    must be a participant in the conversation.

    **Path Params**
    - `conversation_id`: Conversation UUID

    **Returns**
    - Ordered list of messages (oldest → newest)

    **Errors**
    - 401: Unauthorized
    - 403: User is not a participant
    - 404: Conversation not found
    - 500: Database error
    """
    token = credentials.credentials
    user_data = supabase.auth.get_user(jwt=token)
    user_id = user_data.user.id

    # Ensure user belongs to conversation
    membership_check = (
        supabase.table("conversation_members")
        .select("id")
        .eq("conversation_id", conversation_id)
        .eq("user_id", str(user_id))
        .limit(1)
        .execute()
    )

    if not membership_check.data:
        raise HTTPException(status_code=403, detail="Access denied.")

    messages = (
        supabase.table("messages")
        .select("id, sender_id, content, created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )

    return {"messages": messages.data}


@router.get(
    "/conversations",
    # response_model=GetConversationsResponseModel,
    status_code=200,
)
def get_conversations(
    user=Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    List conversations for the authenticated user.

    Returns all conversations the user is a member of. This endpoint is used
    to populate the chat sidebar / conversation list in the frontend.

    **Returns**
    - List of conversations with metadata (conversation_id, is_group, created_at)

    **Errors**
    - 401: Unauthorized
    - 500: Database error
    """
    token = credentials.credentials
    user_data = supabase.auth.get_user(jwt=token)
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
            item["conversations"]
            for item in conversations.data
            if item["conversations"]
        ]
    }
