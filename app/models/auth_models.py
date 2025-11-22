from pydantic import BaseModel, SecretStr, field_validator
import re


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
