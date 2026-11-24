import uuid

import pytest


def url(request_id):
    return f"/friend-request/{request_id}/cancel"


@pytest.fixture
async def outgoing_friend_request(db_session, base_user, other_users):
    """A pending request `base_user` sent, which only they may cancel."""

    from app.friendship.models import FriendShipRequestModel

    friend_request = FriendShipRequestModel(sender_id=base_user.id, receiver_id=other_users[0].id)

    db_session.add(friend_request)
    await db_session.commit()
    await db_session.refresh(friend_request)

    return friend_request


@pytest.fixture
async def receiver_client(client, other_users):
    """The signed-in user is the one the request was sent to."""

    from app.auth.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: other_users[0]

    yield client

    app.dependency_overrides.pop(get_current_user, None)


class TestCancelFriendRequest:
    async def test_success_cancel_friend_request(self, authed_client, outgoing_friend_request):
        response = await authed_client.patch(url(outgoing_friend_request.id))

        assert response.status_code == 200

    async def test_response_status_is_cancelled(self, authed_client, outgoing_friend_request):
        response = await authed_client.patch(url(outgoing_friend_request.id))

        assert response.json()["status"] == "cancelled"

    async def test_row_status_is_cancelled(self, authed_client, db_session, outgoing_friend_request):
        from app.friendship.models import FriendShipRequestModel, Status

        await authed_client.patch(url(outgoing_friend_request.id))

        friend_request = await db_session.get(FriendShipRequestModel, outgoing_friend_request.id)

        assert friend_request.status == Status.CANCELLED

    async def test_creates_no_friendship(self, authed_client, db_session, outgoing_friend_request):
        from sqlalchemy import func, select

        from app.friendship.models import FriendShipModel

        await authed_client.patch(url(outgoing_friend_request.id))

        total = await db_session.scalar(select(func.count()).select_from(FriendShipModel))

        assert total == 0

    async def test_cancelling_twice_returns_409(self, authed_client, outgoing_friend_request):
        await authed_client.patch(url(outgoing_friend_request.id))

        response = await authed_client.patch(url(outgoing_friend_request.id))

        assert response.status_code == 409

    async def test_accepted_request_cannot_be_cancelled(self, authed_client, db_session, outgoing_friend_request):
        from app.friendship.models import Status

        outgoing_friend_request.status = Status.ACCEPTED
        await db_session.commit()

        response = await authed_client.patch(url(outgoing_friend_request.id))

        assert response.status_code == 409

    async def test_receiver_cannot_cancel(self, receiver_client, outgoing_friend_request):
        response = await receiver_client.patch(url(outgoing_friend_request.id))

        assert response.status_code == 404

    async def test_cannot_cancel_a_request_sent_to_you(self, authed_client, incoming_friend_requests):
        response = await authed_client.patch(url(incoming_friend_requests[0].id))

        assert response.status_code == 404

    async def test_unknown_request_returns_404(self, authed_client):
        response = await authed_client.patch(url(uuid.uuid4()))

        assert response.status_code == 404

    async def test_malformed_id_returns_422(self, authed_client):
        response = await authed_client.patch(url("nope"))

        assert response.status_code == 422

    async def test_without_token_returns_401(self, client, outgoing_friend_request):
        response = await client.patch(url(outgoing_friend_request.id))

        assert response.status_code == 401
