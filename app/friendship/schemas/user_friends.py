import datetime
import uuid

from pydantic import BaseModel


class UserFriendsResponse(BaseModel):
    """
    One friend, flattened.

    The `friendship` row holds two user ids and the caller is always one of
    them, so returning the raw row would make every client work out which side
    it is. The query resolves that and returns the other person instead.
    """

    id: uuid.UUID
    friend_id: uuid.UUID
    friend_username: str
    friends_since: datetime.datetime
