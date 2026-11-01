from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import UserModel
from app.db import get_db
from app.friendship.models import FriendShipRequestModel
from app.friendship.schemas import FriendRequestResponse

router = APIRouter()


@router.get(
    "",
    summary="Get all users friend requests",
    status_code=status.HTTP_200_OK,
    response_model=list[FriendRequestResponse],
)
async def user_friend_requests(
    current_user: Annotated[UserModel, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    List every friend request involving the signed-in user.

    **Endpoint:** GET `/friend-request`

    **Authentication:** `Authorization: Bearer <access_token>` required. The list
    is always scoped to the account the token identifies, so there is no way to
    read someone else's requests.

    Both directions come back in one list. Compare `sender_id` to your own id to
    tell them apart: equal means you sent it, otherwise you received it.

    ---

    ## Request

    No body, no parameters.

    ---

    ## Responses

    ### 200 OK
    Every request where the user is the sender or the receiver, in whatever order
    Postgres returns them. An empty list when there are none, which is not an
    error.

    ```json
    [
        {
            "id": "8140e165-a1fe-49b7-bba4-dbf93d6433a5",
            "sender_id": "8b8e715d-d4fb-40a2-91c2-c22a5f61ef53",
            "receiver_id": "ca2b90d1-bc0a-4025-af81-1afb1c294a5b",
            "status": "pending",
            "created_at": "2026-11-01T10:53:56.921650+00:00"
        }
    ]
    ```

    `status` is one of `pending`, `accepted`, `declined`, or `cancelled`. All four
    are returned — this endpoint does not filter by status.

    ### 401 Unauthorized
    The access token is missing, expired, or not an access token.

    ```json
    {
        "detail": "Could not validate credentials."
    }
    ```

    \f

    TODO: add a response_model, status filtering, ordering by created_at, and
    the other user's username so the client does not need a second lookup
    """

    result = await db.scalars(
        select(FriendShipRequestModel).where(
            or_(  # grab req i sent or receive
                FriendShipRequestModel.sender_id == current_user.id,
                FriendShipRequestModel.receiver_id == current_user.id,
            )
        )
    )

    all_request_ids = result.all()

    return all_request_ids
