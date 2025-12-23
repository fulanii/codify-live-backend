from app.core.supabase_client import supabase
from fastapi import HTTPException
from uuid import UUID


def get_username(id: UUID) -> str:
    """Get a user username using there id"""

    try:
        response = (
            supabase.table("profiles")
            .select("username")
            .eq("id", str(id))
            .limit(1)
            .execute()
        )

        return response.data[0]["username"]
    except Exception:
        raise HTTPException(500, detail="Database error while looking up receiver.")
