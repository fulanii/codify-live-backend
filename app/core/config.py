from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: SecretStr
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: SecretStr
    PRODUCTION: bool
    COOKIE_DOMAIN: str | None = None
    ORIGINS: str
    GOOGLE_REDIRECT_URI: str
    GOOGLE_AUTHORIZE_URL: str
    GOOGLE_TOKEN_URL: str
    GOOGLE_SCOPES: str

    @property
    def refresh_token_max_age(self) -> int:
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    @property
    def origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
