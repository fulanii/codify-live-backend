from enum import StrEnum

from pwdlib import PasswordHash
from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

_hasher = PasswordHash.recommended()


class AuthProvider(StrEnum):
    GOOGLE = "google"
    GOOGLE_PASSWORD = "google_password"


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str | None] = mapped_column(
        String, nullable=True, deferred=True
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auth_provider: Mapped[str] = mapped_column(
        String(20), default=AuthProvider.GOOGLE, nullable=False
    )

    def set_password(self, plaintext_password: str) -> None:
        self.password_hash = _hasher.hash(plaintext_password)

    def verify_password(self, plain_password: str) -> bool:
        if self.password_hash is None:  # Google sign in users
            return False
        return _hasher.verify(plain_password, self.password_hash)
