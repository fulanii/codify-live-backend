from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.dependencies import get_current_user
from app.auth.models import UserModel
from app.auth.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get(
    "/me",
    summary="Get user info using the bearer token",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def me(current_user: Annotated[UserModel, Depends(get_current_user)]):
    """
    TODO: Add loggging, rate limitting and tests

    Return the profile of the user the access token belongs to.

    **Endpoint:** GET `/auth/me`

    **Authentication:** `Authorization: Bearer <access_token>` required.

    ---

    ## Request

    No body and no query parameters. The user is identified entirely by the
    token's `sub` claim.

    | Header        | Type   | Required | Description                    |
    |---------------|--------|----------|--------------------------------|
    | Authorization | string | Yes      | `Bearer <access_token>`        |

    ---

    ## Responses

    ### 200 OK

    ```json
    {
        "id": "0f8fad5b-d9cb-469f-a165-70867728950e",
        "name": "Yassine",
        "email": "yassine@yassinecodes.dev",
        "is_verified": true,
        "is_active": true,
        "auth_provider": "google_password"
    }
    ```

    ### 401 Unauthorized
    The token is missing, malformed, expired, not an access token, or names a
    user that no longer exists.

    ```json
    {
        "detail": "Could not validate credentials."
    }
    ```

    The client treats this as "try `/auth/refresh` once, then log in".

    ### 403 Forbidden
    The token is valid but the account has been deactivated. Refreshing will not
    help, so the client should log out rather than retry.

    ```json
    {
        "detail": "This account has been deactivated."
    }
    ```

    ---

    ## Notes

    This is the endpoint the frontend calls on page load to restore a session:
    the access token lives in memory only, so after a reload it refreshes first
    and then calls this to learn who it is logged in as.

    All the work happens in the `get_current_user` dependency — decoding,
    asserting `type == "access"`, and loading the row. `password_hash` is a
    deferred column and `UserResponse` does not declare it, so it is never
    loaded or serialised.
    """

    return current_user
