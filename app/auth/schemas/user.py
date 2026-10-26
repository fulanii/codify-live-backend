import uuid

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str | None
    name: str
    email: str
    is_verified: bool
    is_active: bool
    auth_provider: str
