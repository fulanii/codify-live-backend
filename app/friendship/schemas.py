from pydantic import BaseModel, SecretStr, field_validator
from typing import List, Dict
from datetime import datetime
from uuid import UUID


# Friend search
class Data(BaseModel):
    username: str
    id: str


class FriendsSearchResponseModel(BaseModel):
    usernames: List[Data]


# friend request
class FriendRequestModel(BaseModel):
    receiver_username: str


class FriendRequestDetail(BaseModel):
    id: UUID
    sender_id: UUID
    receiver_id: UUID
    status: str
    created_at: datetime


class FriendRequestResponseModel(BaseModel):
    message: str
    request: FriendRequestDetail


# accept_friend_request
class AcceptFriendRequestDetail(BaseModel):
    friendship_id: UUID
    sender_id: UUID
    receiver_id: UUID
    created_at: datetime


class AcceptFriendRequestModel(BaseModel):
    sender_id: UUID


class FriendshipDetails(BaseModel):
    friendship_id: UUID
    user1_id: UUID
    user2_id: UUID
    created_at: datetime


class AcceptFriendRequestResponseModel(BaseModel):
    friendship_accept: bool
    details: FriendshipDetails


# Decline friendship request
class DeclineFriendshipRequestResponseModel(BaseModel):
    request_declined: bool


# canel sent friend requiest
class CancelFriendshipRequestResponseModel(BaseModel):
    request_canceled: bool


# remove friend
class RemoveFriendResponseModel(BaseModel):
    friend_removed: bool
