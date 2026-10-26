from http.cookies import SimpleCookie


class TestLogin:
    async def test_success_login(self, client, user_password):
        response = await client.post(
            "/auth/login", json={"email": "mike@mike.dev", "password": "SuperSecretPassword123@"}
        )

        access_token = response.json()["access_token"]

        assert response.status_code == 200

        assert response.json() == {
            "id": str(user_password.id),
            "username": user_password.username,
            "name": user_password.name,
            "email": user_password.email,
            "is_verified": user_password.is_verified,
            "is_active": user_password.is_active,
            "auth_provider": user_password.auth_provider,
            "access_token": access_token,
        }

    async def test_refresh_token_set_as_httponly_cookie(self, client, user_password):
        response = await client.post(
            "/auth/login", json={"email": "mike@mike.dev", "password": "SuperSecretPassword123@"}
        )

        jar = SimpleCookie()
        jar.load(response.headers["set-cookie"])
        cookie = jar["refresh"]

        assert cookie.value
        assert cookie["httponly"]
        assert cookie["samesite"] == "Lax"
        assert cookie["path"] == "/auth"

    async def test_wrong_password_returns_401(self, client, user_password):
        response = await client.post("/auth/login", json={"email": "mike@mike.dev", "password": "WrongPassword123@"})

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials."

    async def test_unknown_email_returns_same_401_as_wrong_password(self, client, user_password):
        response = await client.post(
            "/auth/login", json={"email": "nobody@mike.dev", "password": "SuperSecretPassword123@"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials."

    async def test_google_only_user_cannot_login_with_password(self, client, base_user):
        response = await client.post(
            "/auth/login", json={"email": base_user.email, "password": "SuperSecretPassword123@"}
        )

        assert response.status_code == 401

    async def test_unverified_user_returns_403(self, client, db_session):
        from app.auth.models import AuthProvider, UserModel

        user = UserModel(
            name="unverified",
            email="unverified@mike.dev",
            is_verified=False,
            auth_provider=AuthProvider.GOOGLE_PASSWORD,
        )
        user.set_password("SuperSecretPassword123@")
        db_session.add(user)
        await db_session.commit()

        response = await client.post(
            "/auth/login", json={"email": "unverified@mike.dev", "password": "SuperSecretPassword123@"}
        )

        assert response.status_code == 403

    async def test_inactive_user_returns_403(self, client, db_session):
        from app.auth.models import AuthProvider, UserModel

        user = UserModel(
            name="inactive",
            email="inactive@mike.dev",
            is_verified=True,
            is_active=False,
            auth_provider=AuthProvider.GOOGLE_PASSWORD,
        )
        user.set_password("SuperSecretPassword123@")
        db_session.add(user)
        await db_session.commit()

        response = await client.post(
            "/auth/login", json={"email": "inactive@mike.dev", "password": "SuperSecretPassword123@"}
        )

        assert response.status_code == 403
