import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import UserModel
from app.db import get_db

router = APIRouter(prefix="/friend-requests", tags=["Friendship"])


@router.post(
    "",
    summary="Send a friend request",
    status_code=status.HTTP_201_CREATED,
)
async def send_friend_request(
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    receiver_id: Annotated[uuid.UUID, Query()],
):
    """
    TODO: Add logging, rate limitting and tests

    make sure receiver exist
    make sure users not friends
    create friendship request

    fake test uuid: 6b8eea9f-9ddb-4988-803b-c2c482efcab6
    """

    query = select(UserModel.id).where(UserModel.id == receiver_id).exists()
    receiver_exists = await db.scalar(select(query))

    # dont let user know user with id doesn't exist
    if not receiver_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create friendship request.",
        )

    # check users not already friends

    return current_user
