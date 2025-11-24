import os
from dotenv import load_dotenv
from typing import Union

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from .auth import routers as auth_router
from .core.dependencies import verify_token

load_dotenv()

app = FastAPI()
app.include_router(auth_router.router, prefix="/auth", tags=["Authentication"])

# TODO: update origins for prod
origins = [
    "http://localhost:5173",
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
