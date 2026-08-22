import re
from typing import Self

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator


class SetUserPassword(BaseModel):
    password: SecretStr = Field(min_length=8, max_length=32)
    confirm_password: SecretStr = Field(min_length=8, max_length=32)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: SecretStr) -> SecretStr:
        password_raw = value.get_secret_value()

        if not re.search(r"[A-Z]", password_raw):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", password_raw):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"[0-9]", password_raw):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[@$!%*?&]", password_raw):
            raise ValueError("Password must contain at least one special character (@$!%*?&).")

        return value

    @model_validator(mode="after")
    def verify_password_match(self) -> Self:
        if self.password.get_secret_value() != self.confirm_password.get_secret_value():
            raise ValueError("Passwords do not match.")
        return self
