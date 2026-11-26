import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ.setdefault("EMEA_GUARD_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("EMEA_GUARD_JWT_SECRET", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # lifespan seeds the synthetic dataset
        yield c


def _register(client, username, password="Str0ngPassw0rd!"):
    r = client.post("/api/auth/register", json={"username": username, "email": f"{username}@example.com", "password": password})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.services.accounts import limiter
    limiter.reset()


@pytest.fixture(scope="session")
def admin(client):
    headers, body = _register(client, "gov_admin")
    assert body["role"] == "admin", "first account must become admin"
    return headers


@pytest.fixture(scope="session")
def analyst(client, admin):
    headers, body = _register(client, "gov_analyst")
    assert body["role"] == "analyst"
    return headers


@pytest.fixture(scope="session")
def auditor(client, admin):
    headers, body = _register(client, "gov_auditor")
    users = client.get("/api/users", headers=admin).json()
    uid = next(u["id"] for u in users if u["username"] == "gov_auditor")
    assert client.patch(f"/api/users/{uid}", headers=admin, json={"app_role": "auditor"}).status_code == 200
    r = client.post("/api/auth/login", data={"username": "gov_auditor", "password": "Str0ngPassw0rd!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()
