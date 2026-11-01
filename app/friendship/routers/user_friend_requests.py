from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

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
    tell them apart: equal means you sent it, otherwise you received it. Each row
    carries both usernames, so the client can label the other person without a
    second lookup.

    ---

    ## Request

    No body, no parameters.

    ---

    ## Responses

    ### 200 OK
    Every request where the user is the sender or the receiver, newest first. An
    empty list when there are none, which is not an error.

    ```json
    [
        {
            "id": "8140e165-a1fe-49b7-bba4-dbf93d6433a5",
            "sender_id": "8b8e715d-d4fb-40a2-91c2-c22a5f61ef53",
            "sender_username": "prismOrbit32",
            "receiver_id": "ca2b90d1-bc0a-4025-af81-1afb1c294a5b",
            "receiver_username": "vaporNimbus14",
            "status": "pending",
            "created_at": "2026-11-01T10:53:56.921650+00:00"
        }
    ]
    ```

    `status` is one of `pending`, `accepted`, `declined`, or `cancelled`. All four
    are returned — this endpoint does not filter by status.

    Only ids and usernames are exposed. `users` is joined twice, once per side,
    but `response_model` strips everything else, so emails and account flags
    never reach the client.

    ### 401 Unauthorized
    The access token is missing, expired, or not an access token.

    ```json
    {
        "detail": "Could not validate credentials."
    }
    ```

    ---

    ## Notes

    `users` appears twice in the query, so each side needs its own `aliased()`
    copy — without them the join conditions would both point at the same table
    reference and the query would be ambiguous.

    The select lists individual columns rather than whole entities, so the rows
    come back with `.mappings().all()`. `scalars()` would return only the first
    column, which is how this endpoint previously returned a bare list of ids.

    Ordered by `created_at` descending, so the response is stable instead of
    whatever order the planner happens to produce.

    \f

    TODO: filter by status, and paginate once the list can grow
    """

    sender = aliased(UserModel)
    receiver = aliased(UserModel)

    query = (
        select(
            FriendShipRequestModel.id,
            FriendShipRequestModel.sender_id,
            FriendShipRequestModel.receiver_id,
            FriendShipRequestModel.status,
            FriendShipRequestModel.created_at,
            sender.username.label("sender_username"),
            receiver.username.label("receiver_username"),
        )
        .join(sender, sender.id == FriendShipRequestModel.sender_id)
        .join(receiver, receiver.id == FriendShipRequestModel.receiver_id)
        .where(
            or_(
                FriendShipRequestModel.sender_id == current_user.id,
                FriendShipRequestModel.receiver_id == current_user.id,
            )
        )
        .order_by(FriendShipRequestModel.created_at.desc())
    )

    result = await db.execute(query)
    return result.mappings().all()
