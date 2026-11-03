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
    "/{request_id}/decline",
    summary="Decline a friend request",
    status_code=status.HTTP_200_OK,
    response_model=FriendStatusUpdate,
    responses={
        404: {"description": "No request with that id addressed to you"},
        409: {"description": "The request has already been answered"},
    },
)
async def decline_friend_request(
    request_id: uuid.UUID,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    TODO: Add logging, tests and rate limiting

    Decline a pending friend request addressed to you.

    **Endpoint:** PATCH `/friend-request/{request_id}/decline`

    **Authentication:** `Authorization: Bearer <access_token>` required. Only the
    receiver of a request can decline it, the mirror of
    `PATCH /friend-request/{request_id}/accept`.

    There is no request body. The row is addressed by its id in the path.

    The row is kept rather than deleted, with its status set to `declined`. That
    leaves a record that the request was answered, so the sender sees an outcome
    instead of their request silently disappearing. No `friendship` row is
    created, which is the only thing that separates this from accepting.

    ---

    ## Path Parameters

    | Field        | Type | Required | Description                      |
    |--------------|------|----------|----------------------------------|
    | `request_id` | UUID | Yes      | The id of the request to decline |

    ---

    ## Field Validation Rules

    ### request_id
    - Must parse as a UUID, anything else returns 422 before the handler runs.
    - Must belong to an existing request whose `receiver_id` is the caller.
    - That request's status must still be `pending`.

    ---

    ## Responses

    ### 200 OK
    The request is now `declined`. The sender is not notified by this endpoint.

    ```json
    {
        "id": "8140e165-a1fe-49b7-bba4-dbf93d6433a5",
        "sender_id": "8b8e715d-d4fb-40a2-91c2-c22a5f61ef53",
        "receiver_id": "ca2b90d1-bc0a-4025-af81-1afb1c294a5b",
        "status": "declined",
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

    A sender trying to withdraw their own request lands here too. Cancelling is
    `PATCH /friend-request/{request_id}/cancel`.

    ```json
    {
        "detail": "Friend request not found."
    }
    ```

    ### 409 Conflict
    The request exists and is addressed to the caller, but is no longer
    `pending`, so declining twice fails.

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

    ## Decline Flow
    1. The bearer token is resolved to a user by `get_current_user`.
    2. The row is fetched by primary key. A miss raises 404.
    3. The caller is rejected with the same 404 unless they are `receiver_id`.
    4. A status other than `pending` raises 409.
    5. `status` is set to `declined` and committed. One column changes, nothing
        is inserted, so there is no second write to keep in step.

    \f

    Not yet done in this handler:
    - A declined request blocks a new one, because `POST /friend-request`
        rejects any existing row for the pair regardless of status. Either that
        check narrows to `pending`, or declining has to delete the row.
    - The response does not carry usernames, unlike `GET /friend-request`.
    """

    # make sure friend request exist and pending
    friend_request = await db.get(FriendShipRequestModel, request_id)

    if friend_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend request not found.",
        )

    # dont let a non receiver_id learn the request exists
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

    # update friend request status to DECLINED
    friend_request.status = Status.DECLINED
    await db.commit()

    # return new row with updated staus
    return friend_request
