from pydantic import BaseModel


class NewAccessToken(BaseModel):
    access_token: str
