import re
from pydantic import BaseModel, SecretStr, field_validator
from typing import List, Optional
from datetime import datetime


"""
auth/register
"""


class UserRegistrationModel(BaseModel):
    email: str
    username: str
    password: SecretStr

    @field_validator("username")
    @classmethod
    def validate_username(cls, username: str) -> str:
        # Length check (min 3, max 8)
        if not (3 <= len(username) <= 8):
            raise ValueError(
                f"Username must be between 3 and 8 characters long (got {len(username)})."
            )

        # Allow only characters (letters, numbers, underscores, and dots)
        if not re.match(r"^[a-zA-Z0-9_.]+$", username):
            raise ValueError(
                "Username must only contain letters, numbers, underscores, and dots."
            )

        return username.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: SecretStr) -> SecretStr:
        password_str = password.get_secret_value()

        # Minimum length of 8 characters (no maximum)
        if len(password_str) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        # Must include letters (upper and lower), numbers, and special characters.
        password_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*()_+={}\[\]|\\;:'\",.<>?/~`]).{8,}$"

        if not re.match(password_regex, password_str):
            # General error message to covers which types of characters are missing.
            raise ValueError(
                "Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character."
            )

        return password


class UserRegistrationResponseModel(BaseModel):
    id: str
    email: str
    username: str


"""
auth/login
"""


class UserLoginModel(BaseModel):
    email: str
    password: SecretStr


class UserLoginResponseModel(BaseModel):
    access_token: str
    expires_in: int
    user_id: str
    email: str


"""
auth/access
"""


class AccessTokenResponseModel(BaseModel):
    access_token: str


"""
auth/me
"""


class AuthInfo(BaseModel):
    id: str
    email: str


class ProfileInfo(BaseModel):
    username: str
    created_at: datetime


class FriendItem(BaseModel):
    friend_id: str
    username: Optional[str]
    created_at: datetime


class IncomingRequestItem(BaseModel):
    id: str
    sender_id: str
    username: Optional[str]
    status: str
    created_at: datetime


class OutgoingRequestItem(BaseModel):
    id: str
    receiver_id: str
    username: Optional[str]
    status: str
    created_at: datetime


class MeResponseModel(BaseModel):
    auth: AuthInfo
    profile: ProfileInfo
    friends: List[FriendItem]
    incoming_requests: List[IncomingRequestItem]
    outgoing_requests: List[OutgoingRequestItem]
