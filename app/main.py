import os
from dotenv import load_dotenv
from typing import Union

from fastapi import FastAPI, Depends

from .routers import auth
from .dependencies import verify_token

load_dotenv()

app = FastAPI()
app.include_router(auth.router)

@app.get("/protected")
def protected_route(user=Depends(verify_token)):
    return {"message": f"Hello {user['email']}, you are authenticated!"}