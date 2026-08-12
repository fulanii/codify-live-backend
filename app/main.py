import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routers import login_router, logout_router, me_router, refresh_router
from app.core import settings

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(login_router)
app.include_router(logout_router)
app.include_router(refresh_router)
app.include_router(me_router)
