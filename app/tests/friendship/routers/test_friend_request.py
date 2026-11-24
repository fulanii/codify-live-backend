import uuid

URL = "/friend-request"


class TestSendFriendRequest:
    async def test_success_send_friend_request(self, authed_client, other_users):
        response = await authed_client.post(f"{URL}?receiver_id={other_users[0].id}")

        assert response.status_code == 201

    async def test_only_returns_the_new_id(self, authed_client, other_users):
        response = await authed_client.post(f"{URL}?receiver_id={other_users[0].id}")

        assert list(response.json().keys()) == ["id"]

    async def test_row_is_created_pending_with_the_token_user_as_sender(
        self, authed_client, db_session, base_user, other_users
    ):
        from app.friendship.models import FriendShipRequestModel, Status

        response = await authed_client.post(f"{URL}?receiver_id={other_users[0].id}")

        friend_request = await db_session.get(FriendShipRequestModel, uuid.UUID(response.json()["id"]))

        assert friend_request.sender_id == base_user.id
        assert friend_request.receiver_id == other_users[0].id
        assert friend_request.status == Status.PENDING

    async def test_request_to_self_returns_400(self, authed_client, base_user):
        response = await authed_client.post(f"{URL}?receiver_id={base_user.id}")

        assert response.status_code == 400

    async def test_unknown_receiver_returns_400(self, authed_client):
        response = await authed_client.post(f"{URL}?receiver_id={uuid.uuid4()}")

        assert response.status_code == 400

    async def test_inactive_receiver_returns_400(self, authed_client, db_session, other_users):
        other_users[0].is_active = False
        await db_session.commit()

        response = await authed_client.post(f"{URL}?receiver_id={other_users[0].id}")

        assert response.status_code == 400

    async def test_unknown_receiver_message_matches_self_request(self, authed_client, base_user):
        unknown = await authed_client.post(f"{URL}?receiver_id={uuid.uuid4()}")
        to_self = await authed_client.post(f"{URL}?receiver_id={base_user.id}")

        assert unknown.json()["detail"] == to_self.json()["detail"]

    async def test_duplicate_request_returns_409(self, authed_client, other_users):
        await authed_client.post(f"{URL}?receiver_id={other_users[0].id}")

        response = await authed_client.post(f"{URL}?receiver_id={other_users[0].id}")

        assert response.status_code == 409

    async def test_request_in_the_other_direction_returns_409(
        self, authed_client, other_users, incoming_friend_requests
    ):
        response = await authed_client.post(f"{URL}?receiver_id={other_users[0].id}")

        assert response.status_code == 409

    async def test_already_friends_returns_409(self, authed_client, db_session, base_user, other_users):
        from app.friendship.models import FriendShipModel

        first_id, second_id = sorted([base_user.id, other_users[0].id])
        db_session.add(FriendShipModel(user1_id=first_id, user2_id=second_id))
        await db_session.commit()

        response = await authed_client.post(f"{URL}?receiver_id={other_users[0].id}")

        assert response.status_code == 409

    async def test_missing_receiver_id_returns_422(self, authed_client):
        response = await authed_client.post(URL)

        assert response.status_code == 422
        assert any(error["loc"] == ["query", "receiver_id"] for error in response.json()["detail"])

    async def test_malformed_receiver_id_returns_422(self, authed_client):
        response = await authed_client.post(f"{URL}?receiver_id=nope")

        assert response.status_code == 422

    async def test_without_token_returns_401(self, client, other_users):
        response = await client.post(f"{URL}?receiver_id={other_users[0].id}")

        assert response.status_code == 401

    async def test_get_method_not_allowed_on_create(self, authed_client, other_users):
        response = await authed_client.put(f"{URL}?receiver_id={other_users[0].id}")

        assert response.status_code == 405
