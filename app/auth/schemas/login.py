import uuid

from pydantic import BaseModel

from .user import UserResponse


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserLoginResponse(UserResponse):
    access_token: str
