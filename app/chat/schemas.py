from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Dict


# Send Messages
class SendMessageModel(BaseModel):
    conversation_id: UUID
    content: str


class MessageData(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    content: str
    created_at: datetime


class SendMessageResponseModel(BaseModel):
    response_data: list[MessageData]


# Direct messages
class CreateDirectConversationModel(BaseModel):
    receiver_id: UUID


class CreateDirectConversationResponseModel(BaseModel):
    conversation_id: UUID
    is_new: bool


# Get Conversations
class ConversationData(BaseModel):
    id: UUID
    is_group: bool
    created_at: datetime


class GetConversationsResponseModel(BaseModel):
    conversations: List[ConversationData]


# Get messages
class MessagesData(BaseModel):
    id: UUID
    sender_id: UUID
    sender_username: str
    content: str
    created_at: datetime


class GetMessagesResponseModel(BaseModel):
    messages: List[MessagesData]


# Participants
class GetConversationParticipantsResonseModel(BaseModel):
    participant_username: str
    is_friend: bool
