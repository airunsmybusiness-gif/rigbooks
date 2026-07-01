import os
import tempfile

import pytest

# Isolated data dir per test session BEFORE importing the app.
_tmp = tempfile.mkdtemp(prefix="rigbooks-test-")
os.environ["RIGBOOKS_DATA_DIR"] = _tmp
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from rigbooks.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    r = client.post("/api/auth/register", json={
        "email": "driver@example.com", "password": "roadwarrior1",
        "name": "Test Driver"})
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}
