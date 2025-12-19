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
    response_data: List[MessageData]

    # {
    #     "message": [
    #         {
    #             "id": "9aa65976-f9f5-4cd2-8645-7742d0420390",
    #             "conversation_id": "ca396970-f302-463d-a8ff-9d5dc22c50d5",
    #             "sender_id": "10dab277-efaf-4352-a683-287fd8086109",
    #             "content": "whatssup)",
    #             "created_at": "2025-12-14T04:31:26.416852+00:00",
    #         }
    #     ]
    # }
