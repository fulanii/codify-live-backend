from fastapi import APIRouter

from app.auth.schemas import UserLoginRequest, UserLoginResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login/", response_model=UserLoginResponse)
def login(login_data: UserLoginRequest):
    """
    Login for users who set a password, takes email and the password
    """
    # grab email
    # check if user exist by email
    # make sure user is verified and active
    # check password
    # generate jwt token pair
    # refresh in http only cookie
    # access in res model

    # email = login_data.email
    # password = login_data.password

    return
