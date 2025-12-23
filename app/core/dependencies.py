import httpx, os, jwt, base64
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.supabase_client import supabase

load_dotenv()

security = HTTPBearer()
JWT_SIGN_KEY = os.getenv("SUPABASE_JWT_SECRET")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SIGN_KEY,
            algorithms=["HS256"],
            issuer=f"{os.getenv('PUBLIC_SUPABASE_URL')}/auth/v1",
            options={"verify_aud": False},
            leeway=60,
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")

    except jwt.InvalidTokenError as e:
        print("JWT verification failed:", e)
        raise HTTPException(status_code=401, detail="Invalid token")


def get_user_from_token(token: str):
    user = supabase.auth.get_user(token)
    return user
