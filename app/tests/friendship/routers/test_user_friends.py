import pytest


@pytest.fixture
async def friendships(db_session, base_user, other_users):
    """`base_user` friends with all three of `other_users`."""

    from app.friendship.models import FriendShipModel

    rows = []

    for user in other_users:
        first_id, second_id = sorted([base_user.id, user.id])
        rows.append(FriendShipModel(user1_id=first_id, user2_id=second_id))

    db_session.add_all(rows)
    await db_session.commit()

    return rows


class TestUserFriends:
    async def test_success_user_friends(self, authed_client):
        response = await authed_client.get("/friends")

        assert response.status_code == 200

    async def test_no_friends_returns_empty_list(self, authed_client):
        response = await authed_client.get("/friends")

        assert response.json() == []

    async def test_returns_every_friend(self, authed_client, friendships):
        response = await authed_client.get("/friends")

        assert response.status_code == 200
        assert len(response.json()) == 3

    async def test_returns_the_other_user_not_the_caller(self, authed_client, base_user, friendships):
        response = await authed_client.get("/friends")

        friend_ids = [friend["friend_id"] for friend in response.json()]

        assert str(base_user.id) not in friend_ids

    async def test_returns_friend_usernames(self, authed_client, friendships):
        response = await authed_client.get("/friends")

        usernames = [friend["friend_username"] for friend in response.json()]

        assert sorted(usernames) == ["prismOrbit32", "quartzEmber77", "vaporNimbus14"]

    async def test_ordered_by_username(self, authed_client, friendships):
        response = await authed_client.get("/friends")

        usernames = [friend["friend_username"] for friend in response.json()]

        assert usernames == sorted(usernames)

    async def test_returns_expected_fields(self, authed_client, friendships):
        response = await authed_client.get("/friends")

        assert list(response.json()[0].keys()) == ["id", "friend_id", "friend_username", "friends_since"]

    async def test_id_is_the_friendship_not_the_friend(self, authed_client, friendships):
        response = await authed_client.get("/friends")

        returned_ids = {friend["id"] for friend in response.json()}

        assert returned_ids == {str(row.id) for row in friendships}

    async def test_excludes_inactive_friends(self, authed_client, db_session, other_users, friendships):
        other_users[0].is_active = False
        await db_session.commit()

        response = await authed_client.get("/friends")

        usernames = [friend["friend_username"] for friend in response.json()]

        assert other_users[0].username not in usernames
        assert len(usernames) == 2

    async def test_pending_requests_are_not_friends(self, authed_client, incoming_friend_requests):
        response = await authed_client.get("/friends")

        assert response.json() == []

    async def test_excludes_other_peoples_friendships(self, authed_client, db_session, other_users):
        from app.friendship.models import FriendShipModel

        first_id, second_id = sorted([other_users[0].id, other_users[1].id])
        db_session.add(FriendShipModel(user1_id=first_id, user2_id=second_id))
        await db_session.commit()

        response = await authed_client.get("/friends")

        assert response.json() == []

    async def test_without_token_returns_401(self, client):
        response = await client.get("/friends")

        assert response.status_code == 401
