import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp(prefix="oilforge-test-")
os.environ["OILFORGE_DATA_DIR"] = _tmp
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from oilforge.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    r = client.post("/api/auth/register", json={
        "email": "owner@example.com", "password": "forgemaster1",
        "name": "Owner"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
