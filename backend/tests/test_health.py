from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

client = TestClient(app)


def test_health_liveness():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "brewingos-api"
    assert data["epic"] == 1
    assert data["increment"] == 5


@patch("app.main.check_postgres", new_callable=AsyncMock)
@patch("app.main.check_storage")
def test_health_readiness_ok(mock_storage, mock_postgres):
    mock_postgres.return_value = {"status": "ok"}
    mock_storage.return_value = {"status": "ok", "paths": {}}

    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["postgres"]["status"] == "ok"
    assert data["checks"]["storage"]["status"] == "ok"


@patch("app.main.check_postgres", new_callable=AsyncMock)
@patch("app.main.check_storage")
def test_health_readiness_degraded(mock_storage, mock_postgres):
    mock_postgres.return_value = {"status": "error", "detail": "connection refused"}
    mock_storage.return_value = {"status": "ok", "paths": {}}

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"


def test_meta_endpoint():
    class _Result:
        def scalar_one_or_none(self):
            return None

    class _Session:
        async def execute(self, *_args, **_kwargs):
            return _Result()

    async def _override_db():
        yield _Session()

    app.dependency_overrides[get_db] = _override_db
    try:
        response = client.get("/api/v1/meta")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "BrewingOS"
        assert data["epic"] == 1
        assert data["modules"]["infrastructure"] == "active"
        assert data["persistence"]["database"] == "postgresql"
    finally:
        app.dependency_overrides.clear()
