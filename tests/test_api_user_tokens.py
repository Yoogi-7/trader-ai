from typing import AsyncIterator, Tuple

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.api.db import get_async_db
from apps.api.db.base import Base
from apps.api.db.models import User, UserToken
from apps.api.main import app
from apps.api.security import build_token_prefix, hash_token


@pytest.fixture
async def api_client() -> AsyncIterator[Tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_async_db() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_async_db] = override_get_async_db
    original_session_maker = getattr(app.state, "session_maker", None)
    app.state.session_maker = session_maker

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client, session_maker

    app.dependency_overrides.pop(get_async_db, None)
    if original_session_maker is not None:
        app.state.session_maker = original_session_maker
    elif hasattr(app.state, "session_maker"):
        delattr(app.state, "session_maker")

    await engine.dispose()


async def _create_user(session_maker: async_sessionmaker[AsyncSession], username: str = "alice") -> User:
    async with session_maker() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            hashed_password="hashed-password",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _seed_token(
    session_maker: async_sessionmaker[AsyncSession],
    user: User,
    name: str,
    raw_token: str,
) -> UserToken:
    async with session_maker() as session:
        token = UserToken(
            user_id=user.id,
            name=name,
            token_hash=hash_token(raw_token),
            token_prefix=build_token_prefix(raw_token),
            revoked=False,
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)
        return token


@pytest.mark.asyncio
async def test_create_user_token_persists_hash(api_client):
    client, session_maker = api_client
    user = await _create_user(session_maker, "alice")
    bootstrap_token_value = "bootstrap-token"
    await _seed_token(session_maker, user, "bootstrap", bootstrap_token_value)

    response = await client.post(
        f"/api/v1/users/{user.id}/tokens",
        json={"name": "integration"},
        headers={"X-API-Key": bootstrap_token_value},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "integration"
    assert payload["token_prefix"] == payload["token"][: len(payload["token_prefix"])]

    new_token_value = payload["token"]
    async with session_maker() as session:
        result = await session.execute(
            select(UserToken).where(UserToken.id == payload["id"])
        )
        token = result.scalar_one()
        assert token.token_hash == hash_token(new_token_value)
        assert token.token_hash != new_token_value


@pytest.mark.asyncio
async def test_list_user_tokens_requires_api_key(api_client):
    client, session_maker = api_client
    user = await _create_user(session_maker, "bob")
    bootstrap_token_value = "bob-bootstrap-token"
    await _seed_token(session_maker, user, "bootstrap", bootstrap_token_value)

    unauthenticated = await client.get(f"/api/v1/users/{user.id}/tokens")
    assert unauthenticated.status_code == 401

    response = await client.get(
        f"/api/v1/users/{user.id}/tokens",
        headers={"X-API-Key": bootstrap_token_value},
    )
    assert response.status_code == 200
    tokens = response.json()
    assert len(tokens) == 1
    assert tokens[0]["name"] == "bootstrap"


@pytest.mark.asyncio
async def test_revoke_user_token_marks_as_revoked(api_client):
    client, session_maker = api_client
    user = await _create_user(session_maker, "carol")
    bootstrap_token_value = "carol-bootstrap-token"
    await _seed_token(session_maker, user, "bootstrap", bootstrap_token_value)

    creation = await client.post(
        f"/api/v1/users/{user.id}/tokens",
        json={"name": "to-revoke"},
        headers={"X-API-Key": bootstrap_token_value},
    )
    token_id = creation.json()["id"]

    revoke_response = await client.delete(
        f"/api/v1/users/{user.id}/tokens/{token_id}",
        headers={"X-API-Key": bootstrap_token_value},
    )

    assert revoke_response.status_code == 200
    data = revoke_response.json()
    assert data["revoked"] is True

    async with session_maker() as session:
        result = await session.execute(
            select(UserToken).where(UserToken.id == token_id)
        )
        token = result.scalar_one()
        assert token.revoked is True
