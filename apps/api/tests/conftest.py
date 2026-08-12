import os

if os.environ.get("TEST_USE_POSTGRES") != "1":
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./.test-brewing.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["BOOTSTRAP_ADMIN_USERNAME"] = "brewer"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "test-password-not-a-secret"
os.environ["SESSION_SECRET"] = "test-session-secret-with-at-least-32-characters"

import pytest
from fastapi.testclient import TestClient

from brewing_api.domain import model_registry  # noqa: F401
from brewing_api.main import app
from brewing_api.platform.database import Base, engine


@pytest.fixture(autouse=True)
def clean_database():
    if os.environ.get("TEST_USE_POSTGRES") == "1":
        yield
        return
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "brewer", "password": "test-password-not-a-secret"},
    )
    assert response.status_code == 200
    return client


@pytest.fixture
def recipe_payload():
    return {
        "name": "Architecture Ale",
        "target_mash_temperature": "152.00",
        "target_mash_ph": "5.30",
        "mash_ph_tolerance": "0.05",
        "target_mash_gravity": "1.050",
        "mash_gravity_tolerance": "0.003",
        "planned_mash_duration_minutes": 1,
    }


@pytest.fixture
def active_mash(authenticated_client: TestClient, recipe_payload: dict):
    recipe = authenticated_client.post("/api/v1/recipes", json=recipe_payload).json()
    session_response = authenticated_client.post(
        "/api/v1/brew-sessions", json={"recipe_version_id": recipe["version_id"]}
    )
    session_id = session_response.json()["id"]
    authenticated_client.post(f"/api/v1/brew-sessions/{session_id}/start")
    mash_response = authenticated_client.post(
        f"/api/v1/brew-sessions/{session_id}/mash/start"
    )
    return {
        "client": authenticated_client,
        "recipe": recipe,
        "session_id": session_id,
        "stage_id": mash_response.json()["id"],
    }
