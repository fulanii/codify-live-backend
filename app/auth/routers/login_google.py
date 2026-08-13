from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse

from app.core import build_authorize_url

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/login/google", summary="Get redirect url for google login")
async def login_google():
    """
    TODO: Add loggging, rate limitting and tests

    Start the Google sign-in flow by redirecting to Google's consent screen.

    **Endpoint:** GET `/auth/login/google`

    **Authentication:** None required. This is the entry point for users who have
    no session yet.

    ---

    ## Request

    No body, no query parameters, no headers. The client reaches this endpoint by
    navigating the browser to it, not with `fetch` — the response is a redirect
    that the browser must follow to a different origin, and a cross-origin fetch
    would be blocked before it ever got there.

    ---

    ## Responses

    ### 302 Found
    A `Location` header pointing at Google's consent screen, with the
    authorization-code parameters attached:

    | Parameter       | Value                | Purpose                                              |
    |-----------------|----------------------|------------------------------------------------------|
    | `client_id`     | `GOOGLE_CLIENT_ID`   | Identifies this application to Google                |
    | `redirect_uri`  | `GOOGLE_REDIRECT_URI`| Where Google sends the user back with a code         |
    | `response_type` | `code`               | Selects the authorization-code flow                  |
    | `scope`         | `GOOGLE_SCOPES`      | The profile data being requested                     |
    | `access_type`   | `online`             | No Google refresh token — sessions are ours to manage|
    | `prompt`        | `select_account`     | Always show the account chooser                      |

    The `redirect_uri` must match one registered in the Google Cloud console
    exactly, or Google refuses the request before the user sees anything.

    ---

    ## Why the authorization-code flow

    Google never hands a credential to the browser here. It hands back a
    single-use `code`, which the callback exchanges for the user's identity
    server-side, using the client secret. The secret stays on the server and the
    browser never holds anything it could leak.

    `access_type=online` means Google issues no refresh token of its own. Google
    is only used to prove who the user is; the session that follows is the
    application's own access token and rotating refresh cookie, so there is
    nothing from Google worth storing long-term.

    ---

    ## Login Flow
    1. The user clicks "Continue with Google" and the browser navigates here.
    2. This endpoint builds the consent URL and redirects to it.
    3. The user picks an account and grants consent at Google.
    4. Google redirects to `GOOGLE_REDIRECT_URI` with a single-use `code`.
    5. The callback exchanges that code for the user's profile, finds or creates
        the matching user, and issues the normal session — access token plus
        httpOnly refresh cookie.
    """
    return RedirectResponse(url=build_authorize_url(), status_code=status.HTTP_302_FOUND)
