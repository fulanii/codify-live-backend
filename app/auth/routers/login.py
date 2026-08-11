from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.auth.models import UserModel
from app.auth.schemas import UserLoginRequest
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
async def login(login_data: UserLoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    Login for users who set a password, takes email and the password

        {
            "email": "yassine@yassinecodes.dev",
            "password": "7ULDYVwus7m3UTN-"
        }
    """

    # grab email
    email = login_data.email
    password = login_data.password

    # check if user exist by email
    query = select(UserModel).options(undefer(UserModel.password_hash)).where(UserModel.email == email)
    user = await db.execute(query)
    user_data = user.scalar_one_or_none()

    if user_data is None:
        return JSONResponse({"detail": "Invalid credentials."}, status_code=status.HTTP_400_BAD_REQUEST)

    # make sure user is verified and active
    if not user_data.is_verified or not user_data.is_active:
        return JSONResponse(
            {"detail": "You account is not verified, please verify your email first."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # check password
    if not user_data.verify_password(password):
        return JSONResponse({"detail": "Invalid credentials."}, status_code=status.HTTP_400_BAD_REQUEST)

    # generate jwt token pair
    # refresh in http only cookie
    # access in res model

    res_data = {
        "id": user_data.id,
        "name": user_data.name,
        "email": user_data.email,
        "is_verified": user_data.is_verified,
        "is_active": user_data.is_active,
        "access_token": "eyyas.aer.eer",
    }

    return res_data
