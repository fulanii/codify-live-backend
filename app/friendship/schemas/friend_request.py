import datetime
import uuid

from pydantic import BaseModel

from app.friendship.models.friend_request import Status


class FriendRequestCreateResponse(BaseModel):
    id: uuid.UUID


class FriendRequestResponse(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    receiver_id: uuid.UUID
    status: Status
    created_at: datetime.datetime
