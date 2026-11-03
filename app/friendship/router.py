from fastapi import APIRouter

from app.friendship.routers import (
    accept_friend_request,
    cancel_friend_request,
    decline_friend_request,
    friend_request,
    user_friend_requests,
    user_friends,
    users_search,
)

router = APIRouter(tags=["Friendship"])

router.include_router(friend_request.router, prefix="/friend-request")
router.include_router(user_friend_requests.router, prefix="/friend-request")
router.include_router(accept_friend_request.router, prefix="/friend-request")
router.include_router(cancel_friend_request.router, prefix="/friend-request")
router.include_router(decline_friend_request.router, prefix="/friend-request")
router.include_router(users_search.router, prefix="/users")
router.include_router(user_friends.router, prefix="/friends")
