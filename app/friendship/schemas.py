from pydantic import BaseModel, SecretStr, field_validator
from typing import List


class Data(BaseModel):
    username: str
    id: str


class FriendsSearchResponseModel(BaseModel):
    usernames: List[Data]


class FriendRequestModel(BaseModel):
    receiver_username: str
