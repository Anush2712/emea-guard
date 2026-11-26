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


def _token(client, user, pw):
    r = client.post("/api/auth/login", data={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return _token(client, "admin", "admin123")


@pytest.fixture(scope="session")
def analyst(client):
    return _token(client, "analyst", "analyst123")


@pytest.fixture(scope="session")
def auditor(client):
    return _token(client, "auditor", "auditor123")


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()
