"""
update friend request status:
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import UserModel
from app.db import get_db

router = APIRouter()


@router.patch("/{request_id}", summary="Update a friend request status", status_code=status.HTTP_200_OK, responses={})
async def update_friend_status(
    request_id: uuid.UUID,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    #TODO: finish
    """
