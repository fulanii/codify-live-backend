import os
import httpx
from fastapi import APIRouter
from dotenv import load_dotenv
from supabase import create_client, Client


load_dotenv()
router = APIRouter()


supabase_url = os.getenv("PUBLIC_SUPABASE_URL")
supabase_key = os.getenv("SECRET_API_KEY")
service_secret = os.getenv("SERVICE_ROLE_SECRET")

supabase: Client = create_client(supabase_url, supabase_key)
supabase_admin: Client = create_client(supabase_url, service_secret)
