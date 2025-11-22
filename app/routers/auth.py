import os
import httpx
from dotenv import load_dotenv

from fastapi import APIRouter, status, HTTPException

from supabase import AuthApiError

from app.core.supabase_client import supabase
from app.models.auth_models import UserRegistrationModel

router = APIRouter()


@router.post("/register")
def register_user(data: UserRegistrationModel):
    # Check if username already exists
    username_check = (
        supabase.table("profiles").select("id").eq("username", data.username).execute()
    )

    if username_check.data:
        raise HTTPException(status_code=409, detail="Username already taken.")

    # Create Supabase Auth user
    try:
        res = supabase.auth.sign_up(
            {
                "email": data.email,
                "password": data.password.get_secret_value(),
            }
        )
    except AuthApiError as error:
        raise HTTPException(status_code=409, detail=str(error))

    if not res.user:
        raise HTTPException(status_code=400, detail="Failed to create user")

    user_id = res.user.id

    supabase.table("profiles").insert(
        {
            "id": user_id,
            "username": data.username,
        }
    ).execute()

    return {
        "id": user_id,
        "email": res.user.email,
        "username": data.username,
    }


# TODO: Finish login logic
@router.post("/login")
def login_user(email: str, password: str):
    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
    if res.session:
        return {"access_token": res.session.access_token, "user": res.user}
    else:
        raise Exception(res.error.message)
