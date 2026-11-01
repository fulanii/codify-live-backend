from fastapi import APIRouter

from app.friendship.routers import (
    friend_request,
    friend_request_status,
    user_friend_requests,
    users_search,
)

router = APIRouter(tags=["Friendship"])

router.include_router(friend_request.router, prefix="/friend-request")
router.include_router(user_friend_requests.router, prefix="/friend-request")
router.include_router(friend_request_status.router, prefix="/friend-request")
router.include_router(users_search.router, prefix="/users")
