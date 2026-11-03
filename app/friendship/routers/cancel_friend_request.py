import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import UserModel
from app.db import get_db
from app.friendship.models import FriendShipRequestModel, Status
from app.friendship.schemas import FriendStatusUpdate

router = APIRouter()


@router.patch(
    "/{request_id}/cancel",
    summary="Cancel a friend request you sent",
    status_code=status.HTTP_200_OK,
    response_model=FriendStatusUpdate,
    responses={
        404: {"description": "No request with that id sent by you"},
        409: {"description": "The request has already been answered"},
    },
)
async def cancel_friend_request(
    request_id: uuid.UUID,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    TODO: Add logging, tests and rate limiting

    Withdraw a pending friend request you sent.

    **Endpoint:** PATCH `/friend-request/{request_id}/cancel`

    **Authentication:** `Authorization: Bearer <access_token>` required. This is
    the only one of the three transitions the **sender** owns. Accepting and
    declining both belong to the receiver.

    There is no request body. The row is addressed by its id in the path.

    The row is kept rather than deleted, with its status set to `cancelled`.
    Cancelling and declining reach the same end state from opposite sides, so
    the two statuses stay distinct: `cancelled` means the sender changed their
    mind, `declined` means the receiver said no.

    ---

    ## Path Parameters

    | Field        | Type | Required | Description                     |
    |--------------|------|----------|---------------------------------|
    | `request_id` | UUID | Yes      | The id of the request to cancel |

    ---

    ## Field Validation Rules

    ### request_id
    - Must parse as a UUID, anything else returns 422 before the handler runs.
    - Must belong to an existing request whose `sender_id` is the caller.
    - That request's status must still be `pending`.

    ---

    ## Responses

    ### 200 OK
    The request is now `cancelled` and no longer awaits an answer.

    ```json
    {
        "id": "8140e165-a1fe-49b7-bba4-dbf93d6433a5",
        "sender_id": "8b8e715d-d4fb-40a2-91c2-c22a5f61ef53",
        "receiver_id": "ca2b90d1-bc0a-4025-af81-1afb1c294a5b",
        "status": "cancelled",
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
    No request has that id, or one does but the caller is not its sender.
    Both cases return the same body on purpose, so the endpoint cannot be used
    to test whether a given request id exists.

    A receiver trying to turn down a request lands here too. Declining is
    `PATCH /friend-request/{request_id}/decline`.

    ```json
    {
        "detail": "Friend request not found."
    }
    ```

    ### 409 Conflict
    The request exists and was sent by the caller, but is no longer `pending`.
    Cancelling twice fails, and so does cancelling something the receiver has
    already accepted or declined. Removing a friendship that already exists is
    a different operation.

    ```json
    {
        "detail": "This request has already been answered."
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

    ## Cancel Flow
    1. The bearer token is resolved to a user by `get_current_user`.
    2. The row is fetched by primary key. A miss raises 404.
    3. The caller is rejected with the same 404 unless they are `sender_id`.
    4. A status other than `pending` raises 409, so a request the receiver has
        already accepted cannot be cancelled out from under them.
    5. `status` is set to `cancelled` and committed. One column changes.

    \f

    Not yet done in this handler:
    - A cancelled request blocks a new one, because `POST /friend-request`
        rejects any existing row for the pair regardless of status. That makes
        cancelling worse than useless right now: the sender cannot try again.
        Either that check narrows to `pending`, or cancelling deletes the row.
    - The response does not carry usernames, unlike `GET /friend-request`.
    """

    # make sure friend request exist and pending
    friend_request = await db.get(FriendShipRequestModel, request_id)

    if friend_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend request not found.",
        )

    # dont let a non sender learn the request exists
    if friend_request.sender_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend request not found.",
        )

    if friend_request.status != Status.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This request has already been answered.",
        )

    # update friend request status to CANCELLED
    friend_request.status = Status.CANCELLED
    await db.commit()

    # return new row with updated staus
    return friend_request
