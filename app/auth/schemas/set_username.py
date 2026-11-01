import re

from pydantic import BaseModel, Field, field_validator


class SetUserUsername(BaseModel):
    username: str = Field(min_length=3, max_length=30)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        username = value.strip()

        if not re.fullmatch(r"[A-Za-z0-9_-]+", username):
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens.")

        if not username[0].isalnum():
            raise ValueError("Username must start with a letter or a number.")

        return username
