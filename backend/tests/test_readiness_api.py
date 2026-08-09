from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.api.v1.readiness.readiness_service.evaluate_recipe_version", new_callable=AsyncMock)
def test_readiness_endpoint(mock_eval):
    mock_eval.return_value = {
        "recipe_id": "r1",
        "recipe_name": "House IPA",
        "recipe_version_id": "v1",
        "version_number": 1,
        "mutates_inventory": False,
        "mutates_recipe": False,
        "overall": "YELLOW",
        "summary": "READY WITH WARNINGS",
        "checks": [
            {
                "code": "inventory.hop.0",
                "label": "Citra availability",
                "severity": "WARNING",
                "message": "Citra short by 1 oz",
                "details": {},
            }
        ],
        "calculation_snapshot": {},
    }
    response = client.post("/api/v1/recipe-versions/v1/readiness")
    assert response.status_code == 200
    body = response.json()
    assert body["overall"] == "YELLOW"
    assert body["mutates_inventory"] is False
    assert body["mutates_recipe"] is False
