import os
import httpx
from fastapi import APIRouter
from dotenv import load_dotenv
from app.core.supabase_client import supabase


router = APIRouter()


@router.post("/register")
def register_user(email: str, username: str, password: str):
    res = supabase.auth.sign_up({"email": email, "username": username, "password": password})
    if res.user:
        return {"id": res.user.id, "email": res.user.email}
    else:
        raise Exception(res.error.message)


@router.post("/login")
def login_user(email: str, password: str):
    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
    if res.session:
        return {"access_token": res.session.access_token, "user": res.user}
    else:
        raise Exception(res.error.message)
