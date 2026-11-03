from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import UserModel
from app.db import get_db
from app.friendship.models import FriendShipModel
from app.friendship.schemas import UserFriendsResponse

router = APIRouter()


@router.get(
    "",
    summary="Get a user friends",
    status_code=status.HTTP_200_OK,
    response_model=list[UserFriendsResponse],
)
async def user_friends(
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    TODO: Add test, logging, rate limit, pagination

    List the signed-in user's friends.

    **Endpoint:** GET `/friends`

    **Authentication:** `Authorization: Bearer <access_token>` required. The list
    is always the caller's own, so there is no id to pass and no way to read
    somebody else's friends.

    A `friendship` row holds two user ids with the lower one in `user1_id`, and
    the caller is one of them. Which one is an accident of how the two UUIDs
    sort, so the row on its own does not say who the friend is. This endpoint
    resolves that server-side and returns the other person.

    ---

    ## Request

    No body, no parameters.

    ---

    ## Responses

    ### 200 OK
    Every friend of the caller, ordered by username. An empty list when they
    have none, which is not an error.

    Only `id` and `username` are returned for the friend, the same fields as
    `/users/search`. Being someone's friend does not reveal their email.

    ```json
    [
        {
            "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
            "friend_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
            "friend_username": "prismOrbit32",
            "friends_since": "2026-11-01T10:53:56.921650+00:00"
        }
    ]
    ```

    `id` is the friendship row, not the friend. It is what a future
    `DELETE /friends/{id}` would take.

    ### 401 Unauthorized
    The access token is missing, expired, or not an access token.

    ```json
    {
        "detail": "Could not validate credentials."
    }
    ```

    ---

    ## Notes

    ### Picking the other side

    ```python
    friend_id = case(
        (FriendShipModel.user1_id == current_user.id, FriendShipModel.user2_id),
        else_=FriendShipModel.user1_id,
    )
    ```

    `case()` compiles to a SQL `CASE WHEN`, so the choice happens in the
    database and can be used as the join target. That keeps this to one query:
    joining `users` twice and discarding whichever side matched the caller is
    the alternative, and reads worse than the thing it replaces.

    ### Why `mappings()`

    The select lists columns rather than a model, so each row is a `Row` of four
    values. `.mappings().all()` turns those into dicts, which Pydantic reads by
    field name. `.scalars()` would keep only the first column and return a list
    of friendship ids with no usernames, and nothing would error.

    ### Inactive accounts

    The join filters on `UserModel.is_active`, so a deactivated account drops
    out of the list while its `friendship` row stays. Deleting the row would
    throw away the friendship if that account ever comes back.

    ### Ordering

    `ORDER BY username` is explicit. Without it Postgres returns rows in
    whatever order it finds them, which is stable enough to look deliberate in
    development and reshuffles the moment the plan changes.
    """

    # the caller is user1 or user2 depending on how the two uuids sort, so the
    # friend is whichever side is not them
    friend_id = case(
        (FriendShipModel.user1_id == current_user.id, FriendShipModel.user2_id),
        else_=FriendShipModel.user1_id,
    )

    query = (
        select(
            FriendShipModel.id,
            UserModel.id.label("friend_id"),
            UserModel.username.label("friend_username"),
            FriendShipModel.created_at.label("friends_since"),
        )
        .join(UserModel, UserModel.id == friend_id)
        .where(
            or_(
                FriendShipModel.user1_id == current_user.id,
                FriendShipModel.user2_id == current_user.id,
            ),
            UserModel.is_active,
        )
        .order_by(UserModel.username.asc())
    )

    result = await db.execute(query)

    return result.mappings().all()
