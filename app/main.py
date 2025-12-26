import os
from dotenv import load_dotenv
from typing import Union

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from .auth import routers as auth_router
from .friendship import routers as friend_router
from .chat import routers as chat_router

from .core.dependencies import verify_token

load_dotenv()

app = FastAPI()
app.include_router(auth_router.router, prefix="/auth", tags=["Authentication"])
app.include_router(friend_router.router, prefix="/friends", tags=["Friendship"])
app.include_router(chat_router.router, prefix="/chat", tags=["Chat"])


# TODO: update origins for prod
origins = [
    "http://localhost:5173",
    "http://localhost:8080"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# For testing auth purposes
@app.get("/protected")
def protected_route(user=Depends(verify_token)):
    return {"message": f"Hello {user['email']}, you are authenticated!"}
