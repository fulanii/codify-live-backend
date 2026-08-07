from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    google_client_id: str
    google_client_secret: SecretStr

    class Config:
        env_file = ".env"


settings = Settings()
