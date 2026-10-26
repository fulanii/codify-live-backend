from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import UserModel
from app.db import get_db
from app.friendship.schemas import UsersSearchResponse

router = APIRouter(prefix="/users", tags=["Friendship"])


@router.get(
    "/search",
    summary="Search users by username",
    status_code=status.HTTP_200_OK,
    response_model=list[UsersSearchResponse],
)
async def search_users(
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query(min_length=2, max_length=30)],
):
    """
    TODO: Add rate limitting and tests

    Search users by username prefix, for finding someone to add as a friend.

    **Endpoint:** GET `/users/search`

    **Authentication:** `Authorization: Bearer <access_token>` required. Search is
    not public: an anonymous endpoint returning real accounts is a directory
    anyone can scrape.

    ---

    ## Request

    No body. The term is a query parameter.

    | Parameter | Type   | Required | Validation            | Description                   |
    |-----------|--------|----------|-----------------------|-------------------------------|
    | `q`       | string | Yes      | 2 to 30 characters    | Username prefix to search for |

    The minimum length is deliberate. A single character would match a large
    share of the table on every keystroke.

    ---

    ## Responses

    ### 200 OK
    Up to 10 matches, ordered by username. An empty list when nothing matches,
    which is not an error.

    Only `id` and `username` are returned. Email and account flags are left out
    on purpose: searching by name should not hand back everyone's email address.

    ```json
    [
        {
            "id": "0f8fad5b-d9cb-469f-a165-70867728950e",
            "username": "prismOrbit32"
        }
    ]
    ```

    ### 401 Unauthorized
    The access token is missing, expired, or not an access token.

    ```json
    {
        "detail": "Could not validate credentials."
    }
    ```

    ### 422 Unprocessable Entity
    `q` is missing, shorter than 2 characters, or longer than 30.

    ```json
    {
        "detail": [
            {
                "type": "string_too_short",
                "loc": ["query", "q"],
                "msg": "String should have at least 2 characters"
            }
        ]
    }
    ```

    ---

    ## Matching

    The match is a **prefix** (`username ILIKE 'q%'`), case-insensitive, not a
    substring. A leading wildcard would force a sequential scan of the whole
    table on every keystroke, because an index can only seek on a known prefix.
    Prefix matching is also what a typeahead is expected to do.

    Results are capped at 10 and ordered by username, so the response is bounded
    and stable rather than whatever order the planner returns.
    """

    query = (
        select(UserModel.id, UserModel.username)
        .where(UserModel.username.ilike(f"{q}%"), UserModel.id != current_user.id, UserModel.is_active)
        .order_by(UserModel.username.asc())
        .limit(10)
    )

    result = await db.execute(query)
    users = result.mappings().all()

    return users
