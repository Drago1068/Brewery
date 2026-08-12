import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from brewing_api.domain.recipes.models import Recipe, RecipeVersion
from brewing_api.platform.database import SessionLocal


def test_management_endpoint_requires_authentication(client: TestClient):
    response = client.get("/api/v1/recipes")
    assert response.status_code == 401


def test_login_and_create_recipe_version(
    authenticated_client: TestClient, recipe_payload: dict
):
    response = authenticated_client.post("/api/v1/recipes", json=recipe_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Architecture Ale"
    assert body["version_number"] == 1
    assert body["mash_temperature_unit"] == "degF"

    with SessionLocal() as db:
        recipe = db.scalar(select(Recipe).where(Recipe.id == uuid.UUID(body["id"])))
        version = db.scalar(
            select(RecipeVersion).where(RecipeVersion.id == uuid.UUID(body["version_id"]))
        )
        assert recipe is not None
        assert version is not None
        assert version.recipe_id == recipe.id


def test_recipe_validation_rejects_invalid_values(
    authenticated_client: TestClient, recipe_payload: dict
):
    recipe_payload["target_mash_ph"] = "15.00"
    response = authenticated_client.post("/api/v1/recipes", json=recipe_payload)
    assert response.status_code == 422
