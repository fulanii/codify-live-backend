import uuid

import pytest


def url(request_id):
    return f"/friend-request/{request_id}/decline"


@pytest.fixture
async def sender_client(client, other_users):
    """
    Make a client that is logged in as the sender instead of base_user.
    logs in as the wrong party on purpose, to prove the endpoint refuses.

    used by `test_sender_cannot_decline_their_own_request`
    """

    from app.auth.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: other_users[0]

    yield client

    app.dependency_overrides.pop(get_current_user, None)


class TestDeclineFriendRequest:
    async def test_success_decline_friend_request(self, authed_client, incoming_friend_requests):
        response = await authed_client.patch(url(incoming_friend_requests[0].id))

        assert response.status_code == 200

    async def test_response_status_is_declined(self, authed_client, incoming_friend_requests):
        response = await authed_client.patch(url(incoming_friend_requests[0].id))

        assert response.json()["status"] == "declined"

    async def test_row_status_is_declined(self, authed_client, db_session, incoming_friend_requests):
        from app.friendship.models import FriendShipRequestModel, Status

        await authed_client.patch(url(incoming_friend_requests[0].id))

        friend_request = await db_session.get(FriendShipRequestModel, incoming_friend_requests[0].id)

        assert friend_request.status == Status.DECLINED

    async def test_creates_no_friendship(self, authed_client, db_session, incoming_friend_requests):
        from sqlalchemy import func, select

        from app.friendship.models import FriendShipModel

        await authed_client.patch(url(incoming_friend_requests[0].id))

        total = await db_session.scalar(select(func.count()).select_from(FriendShipModel))

        assert total == 0

    async def test_row_is_kept_not_deleted(self, authed_client, db_session, incoming_friend_requests):
        from app.friendship.models import FriendShipRequestModel

        await authed_client.patch(url(incoming_friend_requests[0].id))

        friend_request = await db_session.get(FriendShipRequestModel, incoming_friend_requests[0].id)

        assert friend_request is not None

    async def test_declining_twice_returns_409(self, authed_client, incoming_friend_requests):
        await authed_client.patch(url(incoming_friend_requests[0].id))

        response = await authed_client.patch(url(incoming_friend_requests[0].id))

        assert response.status_code == 409

    async def test_accepted_request_cannot_be_declined(self, authed_client, db_session, incoming_friend_requests):
        from app.friendship.models import Status

        incoming_friend_requests[0].status = Status.ACCEPTED
        await db_session.commit()

        response = await authed_client.patch(url(incoming_friend_requests[0].id))

        assert response.status_code == 409

    async def test_sender_cannot_decline_their_own_request(self, sender_client, incoming_friend_requests):
        response = await sender_client.patch(url(incoming_friend_requests[0].id))

        assert response.status_code == 404

    async def test_unknown_request_returns_404(self, authed_client):
        response = await authed_client.patch(url(uuid.uuid4()))

        assert response.status_code == 404

    async def test_malformed_id_returns_422(self, authed_client):
        response = await authed_client.patch(url("nope"))

        assert response.status_code == 422

    async def test_without_token_returns_401(self, client, incoming_friend_requests):
        response = await client.patch(url(incoming_friend_requests[0].id))

        assert response.status_code == 401
