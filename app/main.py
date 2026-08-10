import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.auth.routers import login_router

logger = logging.getLogger("uvicorn")  # __name__


app = FastAPI(
    title="CodifyLive",
    summary="Api docs for codifylive, built with fastapi.",
    redoc_url=None,
    contact={
        "name": "Yassine",
        "url": "https://yassinecodes.dev",
        "email": "yassine@yassinecodes.dev",
    },
)

app.include_router(login_router)
