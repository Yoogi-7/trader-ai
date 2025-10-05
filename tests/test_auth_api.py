import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.main import app
from apps.api.db import Base, get_db, get_async_db


@pytest.fixture(scope="session")
def db_engines(tmp_path_factory):
    db_dir = tmp_path_factory.mktemp("auth-db")
    db_path = db_dir / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    yield {
        "engine": engine,
        "SessionLocal": SessionLocal,
        "db_path": db_path,
        "db_dir": db_dir,
    }

    engine.dispose()
    if db_path.exists():
        db_path.unlink()
    if db_dir.exists():
        db_dir.rmdir()


@pytest.fixture
def client(db_engines):
    engine = db_engines["engine"]
    SessionLocal = db_engines["SessionLocal"]
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    class AsyncSessionProxy:
        def __init__(self, session):
            self._session = session

        async def execute(self, *args, **kwargs):
            return self._session.execute(*args, **kwargs)

        async def commit(self):
            return self._session.commit()

        async def rollback(self):
            return self._session.rollback()

        async def close(self):
            self._session.close()

        def __getattr__(self, item):
            return getattr(self._session, item)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def override_get_async_db():
        db = SessionLocal()
        proxy = AsyncSessionProxy(db)
        try:
            yield proxy
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_db] = override_get_async_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_register_and_login_flow(client):
    payload = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "supersecret",
    }

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    register_data = response.json()
    assert register_data["user"]["username"] == payload["username"]
    assert register_data["token_type"] == "bearer"

    response = client.post(
        "/api/v1/auth/login",
        json={"username": payload["username"], "password": payload["password"]},
    )
    assert response.status_code == 200
    login_data = response.json()
    assert login_data["user"]["email"] == payload["email"]
    assert "access_token" in login_data


def test_protected_routes_require_authentication(client):
    response = client.get("/api/v1/signals/live")
    assert response.status_code == 401

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password123",
        },
    )
    assert register_response.status_code == 201
    token = register_response.json()["access_token"]

    response = client.get(
        "/api/v1/signals/live",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []
