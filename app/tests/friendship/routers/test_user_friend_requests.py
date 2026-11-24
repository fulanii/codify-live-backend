import pytest

URL = "/friend-request"


@pytest.fixture
async def outgoing_friend_request(db_session, base_user, other_users):
    """One pending request from `base_user`, so the list has both directions."""

    from app.friendship.models import FriendShipRequestModel

    friend_request = FriendShipRequestModel(sender_id=base_user.id, receiver_id=other_users[2].id)

    db_session.add(friend_request)
    await db_session.commit()
    await db_session.refresh(friend_request)

    return friend_request


class TestUserFriendRequests:
    async def test_success_user_friend_requests(self, authed_client):
        response = await authed_client.get(URL)

        assert response.status_code == 200

    async def test_no_requests_returns_empty_list(self, authed_client):
        response = await authed_client.get(URL)

        assert response.json() == []

    async def test_returns_every_received_request(self, authed_client, incoming_friend_requests):
        response = await authed_client.get(URL)

        assert len(response.json()) == 3

    async def test_returns_requests_in_both_directions(
        self, authed_client, base_user, incoming_friend_requests, outgoing_friend_request
    ):
        response = await authed_client.get(URL)

        senders = {item["sender_id"] for item in response.json()}

        assert len(response.json()) == 4
        assert str(base_user.id) in senders

    async def test_includes_the_sender_username(self, authed_client, incoming_friend_requests):
        response = await authed_client.get(URL)

        senders = {item["sender_username"] for item in response.json()}

        assert senders == {"prismOrbit32", "vaporNimbus14", "quartzEmber77"}

    async def test_username_is_null_when_unset(self, authed_client, incoming_friend_requests):
        response = await authed_client.get(URL)

        assert response.json()[0]["receiver_username"] is None

    async def test_returns_expected_fields(self, authed_client, incoming_friend_requests):
        response = await authed_client.get(URL)

        assert list(response.json()[0].keys()) == [
            "id",
            "sender_id",
            "sender_username",
            "receiver_id",
            "receiver_username",
            "status",
            "created_at",
        ]

    async def test_includes_answered_requests(self, authed_client, db_session, incoming_friend_requests):
        from app.friendship.models import Status

        incoming_friend_requests[0].status = Status.DECLINED
        await db_session.commit()

        response = await authed_client.get(URL)

        statuses = {item["status"] for item in response.json()}

        assert statuses == {"pending", "declined"}

    async def test_excludes_other_peoples_requests(self, authed_client, db_session, other_users):
        from app.friendship.models import FriendShipRequestModel

        db_session.add(FriendShipRequestModel(sender_id=other_users[0].id, receiver_id=other_users[1].id))
        await db_session.commit()

        response = await authed_client.get(URL)

        assert response.json() == []

    async def test_without_token_returns_401(self, client):
        response = await client.get(URL)

        assert response.status_code == 401
