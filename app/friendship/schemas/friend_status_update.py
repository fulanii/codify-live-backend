import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.friendship.models.friend_request import Status


class FriendStatusUpdate(BaseModel):
    """
    The row returned by accept, decline and cancel.

    All three change one column and hand back the same request, so they share a
    single response model. Usernames are left out: unlike `GET /friend-request`
    these handlers fetch by primary key and never join `users`.
    """

    id: uuid.UUID
    sender_id: uuid.UUID
    receiver_id: uuid.UUID
    status: Status
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
