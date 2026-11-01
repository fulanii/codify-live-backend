import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import UserModel
from app.db import get_db
from app.friendship.models import FriendShipModel, FriendShipRequestModel
from app.friendship.schemas import FriendRequestCreateResponse

router = APIRouter()


@router.post(
    "",
    summary="Send a friend request",
    status_code=status.HTTP_201_CREATED,
    response_model=FriendRequestCreateResponse,
    responses={
        400: {"description": "Receiver is yourself, or no active user has that id"},
        409: {"description": "Already friends, or a request is already pending"},
    },
)
async def send_friend_request(
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    receiver_id: Annotated[uuid.UUID, Query()],
):
    """
    TODO: Add logging, rate limitting and tests

    Send a friend request to another user.

    **Endpoint:** POST `/friend-request`

    **Authentication:** `Authorization: Bearer <access_token>` required. The sender
    is always the account the token identifies, so the request cannot be used to
    send on someone else's behalf.

    A request is stored as a single row with the two user ids sorted low-to-high in
    `user1_id` and `user2_id`. That ordering is enforced by a check constraint, and
    a unique constraint on the pair means the same two users can never hold two
    rows at once, whichever direction the request was sent in.

    ---

    ## Query Parameters

    | Field         | Type | Required | Description                               |
    |---------------|------|----------|-------------------------------------------|
    | `receiver_id` | UUID | Yes      | The id of the user to send the request to |

    ---

    ## Field Validation Rules

    ### receiver_id
    - Must parse as a UUID — anything else returns 422 before the handler runs.
    - Must not equal the authenticated user's own id.
    - Must belong to an existing user whose `is_active` is true.
    - Inactive accounts are treated exactly like ids that do not exist, so
    deactivating an account hides it here as well as from `/users/search`.

    ---

    ## Responses

    ### 201 Created
    The request row was committed with a status of `pending`.

    ```json
    {
        "id": "9f1c8e2a-3b4d-4c5e-8a7f-1d2e3f4a5b6c"
    }
    ```

    ### 400 Bad Request
    Either `receiver_id` is the caller's own id, or it does not match an active
    user. Both cases return the same message on purpose — a distinct "no such
    user" message would turn this endpoint into a way to test whether a given id
    exists.

    ```json
    {
        "detail": "Unable to create friendship request."
    }
    ```

    ### 409 Conflict
    The two users are already friends:

    ```json
    {
        "detail": "You are already friends with this user."
    }
    ```

    Or a request between them is already awaiting an answer:

    ```json
    {
        "detail": "A friend request is already pending between you and this user."
    }
    ```

    ### 401 Unauthorized
    The access token is missing, expired, or not an access token.

    ```json
    {
        "detail": "Could not validate credentials."
    }
    ```

    ### 422 Unprocessable Entity
    `receiver_id` was absent or not a valid UUID. Raised by FastAPI before the
    handler runs, so `loc` names the query parameter rather than the body.

    ```json
    {
        "detail": [
            {
                "type": "uuid_parsing",
                "loc": ["query", "receiver_id"],
                "msg": "Input should be a valid UUID, invalid length: expected length 32 for simple format, found 5"
            }
        ]
    }
    ```

    ---

    ## Send Request Flow
    1. The bearer token is resolved to a user by `get_current_user`.
    2. The receiver is rejected if it is the caller, then if no active user has
        that id. Both paths raise the same 400.
    3. The two ids are sorted so the lower one lands in `user1_id`, matching the
        check constraint on `friendship` and `friendship_request`.
    4. An existing friendship for that sorted pair raises 409.
    5. A `pending` request for that sorted pair raises 409. Rows in any other
        status are ignored, so a declined request does not block a new one.
    6. The row is inserted with `status` defaulting to `pending` and committed.
        Postgres generates the id, which is returned to the caller.
    """
    sender_id = current_user.id

    # user cant send friend req to themself
    if receiver_id == sender_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create friendship request.",
        )

    receiver_exists = await db.scalar(
        select(select(UserModel.id).where(UserModel.id == receiver_id, UserModel.is_active).exists())
    )

    # dont let user know user with id doesn't exist
    if not receiver_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create friendship request.",
        )

    # friendship check
    first_id, second_id = sorted([sender_id, receiver_id])

    already_friends = await db.scalar(
        select(
            select(FriendShipModel.id)
            .where(FriendShipModel.user1_id == first_id, FriendShipModel.user2_id == second_id)
            .exists()
        )
    )

    if already_friends:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already friends with this user.",
        )

    request_exists = await db.scalar(
        select(
            select(FriendShipRequestModel.id)
            .where(
                or_(
                    and_(
                        FriendShipRequestModel.sender_id == sender_id, FriendShipRequestModel.receiver_id == receiver_id
                    ),
                    and_(
                        FriendShipRequestModel.sender_id == receiver_id, FriendShipRequestModel.receiver_id == sender_id
                    ),
                )
            )
            .exists()
        )
    )

    if request_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A friend request is already pending between you and this user.",
        )

    friend_request = FriendShipRequestModel(sender_id=sender_id, receiver_id=receiver_id)
    db.add(friend_request)
    await db.commit()

    return {"id": friend_request.id}
