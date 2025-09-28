from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api import crud
from apps.api.config import settings
from apps.api.db.session import SessionLocal
from apps.api.security import get_password_hash


def _create_user(email: str, password: str, role: str = "USER") -> None:
    """Ensure a user with given credentials exists for tests."""
    normalized_email = email.strip().lower()
    with SessionLocal() as db:
        existing = crud.user_get_by_email(db, normalized_email)
        if existing:
            db.delete(existing)
            db.commit()
        password_hash = get_password_hash(password)
        crud.user_create(db, normalized_email, password_hash, role=role)


def _login(client: TestClient, email: str, password: str) -> tuple[str, dict]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload["access_token"], payload["user"]


def test_login_and_me_flow() -> None:
    test_email = "tester@example.com"
    test_password = "secret123"
    _create_user(test_email, test_password)

    with TestClient(app) as client:
        token, user_payload = _login(client, test_email, test_password)
        assert user_payload["email"] == test_email
        assert user_payload["role"] == "USER"

        me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_response.status_code == 200
        me_payload = me_response.json()
        assert me_payload["email"] == test_email
        assert me_payload["role"] == "USER"


def test_login_rejects_invalid_password() -> None:
    test_email = "invalid@example.com"
    _create_user(test_email, "correct-pass")

    with TestClient(app) as client:
        response = client.post("/auth/login", json={"email": test_email, "password": "wrong"})
        assert response.status_code == 401
        assert "Invalid credentials" in response.text


def test_admin_only_routes_require_admin_role() -> None:
    regular_email = "regular@example.com"
    regular_password = "userpass"
    _create_user(regular_email, regular_password)

    with TestClient(app) as client:
        user_token, _ = _login(client, regular_email, regular_password)
        forbidden_resp = client.get("/users", headers={"Authorization": f"Bearer {user_token}"})
        assert forbidden_resp.status_code == 403

        admin_token, admin_payload = _login(client, settings.admin_email, settings.admin_password)
        users_resp = client.get("/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert users_resp.status_code == 200
        emails = [entry["email"] for entry in users_resp.json()]
        assert admin_payload["email"] in emails
        assert regular_email in emails
