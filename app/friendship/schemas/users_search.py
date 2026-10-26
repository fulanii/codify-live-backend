import uuid

from pydantic import BaseModel


class UsersSearchResponse(BaseModel):
    id: uuid.UUID
    username: str
