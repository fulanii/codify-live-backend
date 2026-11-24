import os
from datetime import UTC, datetime, timedelta

import pytest
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

load_dotenv()
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]


from app.core import settings  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    """
    Build the schema once for the whole run, then tear it down.

    Sync on purpose: Alembic's async env.py calls `asyncio.run()`
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")

    command.upgrade(cfg, "head")

    yield

    command.downgrade(cfg, "base")


@pytest.fixture(scope="session")
def engine():
    """One engine for the whole run, not per test."""

    return create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)


@pytest.fixture
async def db_session(engine):
    """
    A session whose writes are discarded at the end of the test.
    """

    async with engine.connect() as connection:
        transaction = await connection.begin()

        session_factory = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async with session_factory() as session:
            yield session

        await transaction.rollback()


@pytest.fixture
async def client(db_session: AsyncSession):
    """An AsyncClient wired to the app, sharing the test's session and rollback."""
    from httpx import ASGITransport, AsyncClient

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def base_user(db_session):
    """A verified, active user other tests can authenticate as or collide against."""

    from app.auth.models import UserModel

    user = UserModel(name="Yassine", email="yassine@yassinecodes.dev", is_verified=True)

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest.fixture
async def user_password(db_session):
    """A verified, active user with password."""

    from app.auth.models import AuthProvider, UserModel

    user = UserModel(
        name="mike",
        email="mike@mike.dev",
        is_verified=True,
        auth_provider=AuthProvider.GOOGLE_PASSWORD,
    )
    user.set_password("SuperSecretPassword123@")

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest.fixture
async def authed_client(client, base_user):
    """A client whose requests resolve to `base_user`, bypassing real token checks."""

    from app.auth.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: base_user

    yield client

    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def refresh_token(base_user, db_session):
    """
    A valid refresh token for `base_user`
    """

    from app.auth.models import RefreshTokenModel
    from app.core import create_refresh_token

    refresh_token = create_refresh_token()

    refresh_token_data = RefreshTokenModel(
        user_id=base_user.id,
        token_hash=refresh_token["stored"],
        expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )

    db_session.add(refresh_token_data)

    await db_session.commit()
    await db_session.refresh(refresh_token_data)

    return refresh_token_data


@pytest.fixture
async def other_users(db_session):
    """
    Three verified, active users with usernames, to be the other side of a
    friendship or a search hit.
    """

    from app.auth.models import UserModel

    users = [
        UserModel(username="prismOrbit32", name="Ada", email="ada@codifylive.test", is_verified=True),
        UserModel(username="vaporNimbus14", name="Linus", email="linus@codifylive.test", is_verified=True),
        UserModel(username="quartzEmber77", name="Grace", email="grace@codifylive.test", is_verified=True),
    ]

    db_session.add_all(users)
    await db_session.commit()

    for user in users:
        await db_session.refresh(user)

    return users


@pytest.fixture
async def incoming_friend_requests(db_session, base_user, other_users):
    """
    One pending request from each of `other_users` to `base_user`.

    `base_user` is the receiver in all three, so these are the rows accept and
    decline are allowed to act on. Cancel is the sender's, so it needs the
    mirror of this.
    """

    from app.friendship.models import FriendShipRequestModel

    requests = [FriendShipRequestModel(sender_id=user.id, receiver_id=base_user.id) for user in other_users]

    db_session.add_all(requests)
    await db_session.commit()

    for friend_request in requests:
        await db_session.refresh(friend_request)

    return requests


@pytest.fixture
async def friendships(db_session, base_user, other_users):
    from app.friendship.models import FriendShipModel

    rows = [
        FriendShipModel(**dict(zip(("user1_id", "user2_id"), sorted([user.id, base_user.id]), strict=True)))
        for user in other_users
    ]

    db_session.add_all(rows)
    await db_session.commit()

    return rows
