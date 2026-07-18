"""Fixtures pytest partagées pour SafeCity."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest  # noqa: E402

from backend import create_app  # noqa: E402
from backend.config import get_config  # noqa: E402


@pytest.fixture()
def app():
    application = create_app(get_config("testing"))
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def operator_token(client):
    res = client.post(
        "/api/auth/login",
        json={"email": "operateur@safecity.local", "password": "safecity123"},
    )
    return res.get_json()["token"]


@pytest.fixture()
def auth_headers(operator_token):
    return {"Authorization": "Bearer " + operator_token}
