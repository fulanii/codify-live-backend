import uuid

import pytest


def url(request_id):
    return f"/friend-request/{request_id}/accept"


@pytest.fixture
async def sender_client(client, other_users):
    """The signed-in user is the one who sent the request, not its receiver."""

    from app.auth.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: other_users[0]

    yield client

    app.dependency_overrides.pop(get_current_user, None)


class TestAcceptFriendRequest:
    async def test_success_accept_friend_request(self, authed_client, incoming_friend_requests):
        response = await authed_client.patch(url(incoming_friend_requests[0].id))

        assert response.status_code == 200

    async def test_response_status_is_accepted(self, authed_client, incoming_friend_requests):
        response = await authed_client.patch(url(incoming_friend_requests[0].id))

        assert response.json()["status"] == "accepted"

    async def test_row_status_is_accepted(self, authed_client, db_session, incoming_friend_requests):
        from app.friendship.models import FriendShipRequestModel, Status

        await authed_client.patch(url(incoming_friend_requests[0].id))

        friend_request = await db_session.get(FriendShipRequestModel, incoming_friend_requests[0].id)

        assert friend_request.status == Status.ACCEPTED

    async def test_creates_the_friendship_with_sorted_ids(
        self, authed_client, db_session, base_user, other_users, incoming_friend_requests
    ):
        from sqlalchemy import select

        from app.friendship.models import FriendShipModel

        await authed_client.patch(url(incoming_friend_requests[0].id))

        friendship = (await db_session.scalars(select(FriendShipModel))).one()
        first_id, second_id = sorted([base_user.id, other_users[0].id])

        assert friendship.user1_id == first_id
        assert friendship.user2_id == second_id

    async def test_accepting_twice_returns_409(self, authed_client, incoming_friend_requests):
        await authed_client.patch(url(incoming_friend_requests[0].id))

        response = await authed_client.patch(url(incoming_friend_requests[0].id))

        assert response.status_code == 409

    async def test_accepting_twice_creates_one_friendship(self, authed_client, db_session, incoming_friend_requests):
        from sqlalchemy import func, select

        from app.friendship.models import FriendShipModel

        await authed_client.patch(url(incoming_friend_requests[0].id))
        await authed_client.patch(url(incoming_friend_requests[0].id))

        total = await db_session.scalar(select(func.count()).select_from(FriendShipModel))

        assert total == 1

    async def test_sender_cannot_accept_their_own_request(self, sender_client, incoming_friend_requests):
        response = await sender_client.patch(url(incoming_friend_requests[0].id))

        assert response.status_code == 404

    async def test_sender_accept_creates_no_friendship(self, sender_client, db_session, incoming_friend_requests):
        from sqlalchemy import func, select

        from app.friendship.models import FriendShipModel

        await sender_client.patch(url(incoming_friend_requests[0].id))

        total = await db_session.scalar(select(func.count()).select_from(FriendShipModel))

        assert total == 0

    async def test_unknown_request_returns_404(self, authed_client):
        response = await authed_client.patch(url(uuid.uuid4()))

        assert response.status_code == 404

    async def test_declined_request_cannot_be_accepted(self, authed_client, db_session, incoming_friend_requests):
        from app.friendship.models import Status

        incoming_friend_requests[0].status = Status.DECLINED
        await db_session.commit()

        response = await authed_client.patch(url(incoming_friend_requests[0].id))

        assert response.status_code == 409

    async def test_malformed_id_returns_422(self, authed_client):
        response = await authed_client.patch(url("nope"))

        assert response.status_code == 422

    async def test_without_token_returns_401(self, client, incoming_friend_requests):
        response = await client.patch(url(incoming_friend_requests[0].id))

        assert response.status_code == 401
