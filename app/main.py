import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://codifylive.com",
    "https://www.codifylive.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(login_router)
