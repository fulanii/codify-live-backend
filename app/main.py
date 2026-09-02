from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.auth.routers import (
    google_callback_router,
    google_login_router,
    login_router,
    logout_router,
    me_router,
    refresh_router,
    set_passowrd_router,
)
from app.core import limiter, settings

app = FastAPI(
    title="CodifyLive",
    summary="Api docs for codifylive, built with fastapi.",
    redoc_url=None,
    docs_url="/docs" if not settings.PRODUCTION else None,
    contact={
        "name": "Yassine",
        "url": "https://yassinecodes.dev",
        "email": "yassine@yassinecodes.dev",
    },
)

app.state.limiter = limiter

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(google_login_router)
app.include_router(google_callback_router)
app.include_router(set_passowrd_router)
