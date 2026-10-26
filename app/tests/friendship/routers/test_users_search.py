import pytest


@pytest.fixture
async def searchable_users(db_session):
    """Users with usernames, covering prefix, casing and an inactive account."""

    from app.auth.models import UserModel

    users = [
        UserModel(username="yassine", name="Yassine", email="y1@test.dev", is_verified=True),
        UserModel(username="Yasmine", name="Yasmine", email="y2@test.dev", is_verified=True),
        UserModel(username="mikeyassine", name="Mike", email="y3@test.dev", is_verified=True),
        UserModel(username="dylan", name="Dylan", email="y4@test.dev", is_verified=True),
        UserModel(
            username="yasdeactivated",
            name="Deactivated",
            email="y5@test.dev",
            is_verified=True,
            is_active=False,
        ),
    ]

    db_session.add_all(users)
    await db_session.commit()

    return users


class TestUsersSearch:
    async def test_sucess_users_search(self, authed_client):
        response = await authed_client.get(
            "/users/search?q=ya",
        )

        assert response.status_code == 200

    async def test_returns_prefix_matches(self, authed_client, searchable_users):
        response = await authed_client.get("/users/search?q=yas")

        usernames = [user["username"] for user in response.json()]

        assert response.status_code == 200
        assert sorted(usernames) == ["Yasmine", "yassine"]

    async def test_match_is_case_insensitive(self, authed_client, searchable_users):
        response = await authed_client.get("/users/search?q=YASM")

        assert [user["username"] for user in response.json()] == ["Yasmine"]

    async def test_does_not_match_mid_username(self, authed_client, searchable_users):
        response = await authed_client.get("/users/search?q=yassine")

        usernames = [user["username"] for user in response.json()]

        assert "mikeyassine" not in usernames

    async def test_excludes_inactive_users(self, authed_client, searchable_users):
        response = await authed_client.get("/users/search?q=yas")

        usernames = [user["username"] for user in response.json()]

        assert "yasdeactivated" not in usernames

    async def test_excludes_the_current_user(self, authed_client, base_user, db_session, searchable_users):
        base_user.username = "yasself"
        await db_session.commit()

        response = await authed_client.get("/users/search?q=yas")

        usernames = [user["username"] for user in response.json()]

        assert "yasself" not in usernames

    async def test_no_match_returns_empty_list(self, authed_client, searchable_users):
        response = await authed_client.get("/users/search?q=zzz")

        assert response.status_code == 200
        assert response.json() == []

    async def test_only_returns_id_and_username(self, authed_client, searchable_users):
        response = await authed_client.get("/users/search?q=dylan")

        assert list(response.json()[0].keys()) == ["id", "username"]

    async def test_results_are_capped_at_ten(self, authed_client, db_session):
        from app.auth.models import UserModel

        db_session.add_all(
            UserModel(
                username=f"capped{index}",
                name=f"Capped {index}",
                email=f"capped{index}@test.dev",
                is_verified=True,
            )
            for index in range(15)
        )
        await db_session.commit()

        response = await authed_client.get("/users/search?q=capped")

        assert len(response.json()) == 10

    async def test_short_query_returns_422(self, authed_client):
        response = await authed_client.get("/users/search?q=y")

        assert response.status_code == 422

    async def test_missing_query_returns_422(self, authed_client):
        response = await authed_client.get("/users/search")

        assert response.status_code == 422

    async def test_without_token_returns_401(self, client):
        response = await client.get("/users/search?q=ya")

        assert response.status_code == 401
