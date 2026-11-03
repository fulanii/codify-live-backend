import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import UserModel
from app.db import get_db
from app.friendship.models import FriendShipModel, FriendShipRequestModel, Status
from app.friendship.schemas import FriendStatusUpdate

router = APIRouter()


@router.patch(
    "/{request_id}/accept",
    summary="Accept a friend request",
    status_code=status.HTTP_200_OK,
    response_model=FriendStatusUpdate,
    responses={
        404: {"description": "No pending request with that id addressed to you"},
        409: {"description": "Request already answered, or the friendship already exists"},
    },
)
async def accept_friend_request(
    request_id: uuid.UUID,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    TODO: Add logging, tests and rate limiting

    Accept a pending friend request addressed to you.

    **Endpoint:** PATCH `/friend-request/{request_id}/accept`

    **Authentication:** `Authorization: Bearer <access_token>` required. Only the
    receiver of a request can accept it, so the caller cannot answer on someone
    else's behalf.

    There is no request body. The row is addressed by its id in the path, and
    everything else the handler needs is already on that row or on the token.

    ---

    ## Path Parameters

    | Field        | Type | Required | Description                        |
    |--------------|------|----------|------------------------------------|
    | `request_id` | UUID | Yes      | The id of the request to accept    |

    ---

    ## Field Validation Rules

    ### request_id
    - Must parse as a UUID, anything else returns 422 before the handler runs.
    - Must belong to an existing request whose `receiver_id` is the caller.
    - That request's status must still be `pending`.

    ---

    ## Responses

    ### 200 OK
    The request is now `accepted` and a `friendship` row exists for the pair.

    ```json
    {
        "id": "8140e165-a1fe-49b7-bba4-dbf93d6433a5",
        "sender_id": "8b8e715d-d4fb-40a2-91c2-c22a5f61ef53",
        "receiver_id": "ca2b90d1-bc0a-4025-af81-1afb1c294a5b",
        "status": "accepted",
        "created_at": "2026-11-01T10:53:56.921650+00:00"
    }
    ```

    ### 401 Unauthorized
    The access token is missing, expired, or not an access token.

    ```json
    {
        "detail": "Could not validate credentials."
    }
    ```

    ### 404 Not Found
    No request has that id, or one does but the caller is not its receiver.
    Both cases return the same body on purpose. A distinct "not yours" message
    would confirm that a given request id exists.

    ```json
    {
        "detail": "Friend request not found."
    }
    ```

    ### 409 Conflict
    The request exists and belongs to the caller, but is no longer `pending`:

    ```json
    {
        "detail": "This request has already been answered."
    }
    ```

    Or the two users already have a friendship row, which only happens if two
    accepts land at the same time:

    ```json
    {
        "detail": "You are already friends with this user."
    }
    ```

    ### 422 Unprocessable Entity
    `request_id` is not a valid UUID. Raised by FastAPI before the handler runs,
    so `loc` names the path parameter.

    ```json
    {
        "detail": [
            {
                "type": "uuid_parsing",
                "loc": ["path", "request_id"],
                "msg": "Input should be a valid UUID, invalid length: expected length 32 for simple format, found 5"
            }
        ]
    }
    ```

    ---

    ## Accept Flow
    1. The bearer token is resolved to a user by `get_current_user`.
    2. The row is fetched by primary key. A miss raises 404.
    3. The caller is rejected with the same 404 unless they are `receiver_id`.
    4. A status other than `pending` raises 409, so accepting twice fails.
    5. The two ids are sorted, because `friendship` keeps the lower id in
        `user1_id` under a check constraint.
    6. The status change and the new `friendship` row are committed together, in
        one transaction. Either both land or neither does, so there is no state
        where a request reads `accepted` while the users are not friends.
    7. A unique violation on the pair means a concurrent accept won the race.
        The transaction is rolled back and the result is reported as 409.

    \f

    Not yet done in this handler:
    - Declining and cancelling are still missing, so the only way out of
        `pending` is acceptance.
    - The response does not carry usernames, unlike `GET /friend-request`. It
        would need the same double-aliased join to include them.
    """

    # make sure friend request exist and pending
    friend_request = await db.get(FriendShipRequestModel, request_id)

    if friend_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend request not found.",
        )

    # dont let a non receiver learn the request exists
    if friend_request.receiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend request not found.",
        )

    if friend_request.status != Status.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This request has already been answered.",
        )

    # friendship has no direction, the lower id goes first under a check constraint
    first_id, second_id = sorted([friend_request.sender_id, friend_request.receiver_id])

    # update friend request status to ACCEPTED
    friend_request.status = Status.ACCEPTED

    # create friend row record
    db.add(FriendShipModel(user1_id=first_id, user2_id=second_id))

    # one commit, so the request and the friendship can never disagree
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already friends with this user.",
        ) from None

    # return new row with updated staus
    return friend_request
