from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: SecretStr
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    google_client_id: str
    google_client_secret: SecretStr
    PRODUCTION: bool
    COOKIE_DOMAIN: str | None = None

    @property
    def refresh_token_max_age(self) -> int:
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    class Config:
        env_file = ".env"


settings = Settings()
