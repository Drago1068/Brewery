from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db.models import Recipe, RecipeVersion
from app.main import app
from app.schemas.recipe import RecipeCreate

client = TestClient(app)


def test_recipe_create_requires_batch_size():
    with pytest.raises(ValidationError):
        RecipeCreate(
            name="House IPA",
            version={
                "batch_size": "0",
                "batch_size_unit": "gal",
            },
        )


def _recipe() -> Recipe:
    return Recipe(
        id="dddddddd-dddd-dddd-dddd-dddddddddddd",
        brewery_id="11111111-1111-1111-1111-111111111111",
        name="House IPA",
        style="American IPA",
        description="Citrus forward",
        status="ACTIVE",
        current_version_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        created_by="local-brewer",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _version(**overrides) -> RecipeVersion:
    data = {
        "id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        "recipe_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "version_number": 1,
        "parent_version_id": None,
        "change_summary": None,
        "status": "DRAFT",
        "batch_size": Decimal("5"),
        "batch_size_unit": "gal",
        "equipment_profile_id": None,
        "brewhouse_efficiency": Decimal("72"),
        "boil_time_minutes": 60,
        "mash_method": "SINGLE_INFUSION",
        "notes": None,
        "created_by": "local-brewer",
        "approved_by": None,
        "approved_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "intent": None,
        "fermentables": [],
        "hops": [],
        "yeasts": [],
        "adjuncts": [],
        "water_additions": [],
        "mash_steps": [],
        "targets": [],
    }
    data.update(overrides)
    return RecipeVersion(**data)


@patch("app.api.v1.recipes.recipe_service.create_recipe", new_callable=AsyncMock)
def test_create_recipe_api(mock_create):
    recipe = _recipe()
    version = _version()
    mock_create.return_value = {
        "recipe": recipe,
        "versions": [version],
        "current_version": version,
    }
    response = client.post(
        "/api/v1/breweries/11111111-1111-1111-1111-111111111111/recipes",
        json={
            "name": "House IPA",
            "style": "American IPA",
            "version": {
                "batch_size": "5",
                "batch_size_unit": "gal",
                "brewhouse_efficiency": "72",
                "boil_time_minutes": 60,
                "mash_method": "SINGLE_INFUSION",
                "intent": {"overall_objective": "Bright citrus IPA"},
                "fermentables": [
                    {
                        "ingredient_name": "2-Row",
                        "amount": "10",
                        "unit": "lb",
                        "potential_sg": "1.037",
                        "color_lovibond": "2",
                    }
                ],
                "hops": [
                    {
                        "ingredient_name": "Citra",
                        "amount": "1",
                        "unit": "oz",
                        "alpha_acid": "12",
                        "stage": "BOIL",
                        "time_minutes": 60,
                    }
                ],
                "yeasts": [{"ingredient_name": "US-05", "expected_attenuation": "78"}],
                "mash_steps": [
                    {
                        "step_name": "Saccharification",
                        "target_temperature_c": "67",
                        "duration_minutes": 60,
                    }
                ],
            },
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "House IPA"
    assert body["current_version"]["version_number"] == 1
    assert body["current_version"]["status"] == "DRAFT"


@patch("app.api.v1.recipes.recipe_service.create_new_version", new_callable=AsyncMock)
def test_create_new_version_api(mock_create):
    mock_create.return_value = _version(version_number=2, parent_version_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    response = client.post(
        "/api/v1/recipes/dddddddd-dddd-dddd-dddd-dddddddddddd/versions",
        json={
            "change_summary": "More late hops",
            "version": {
                "batch_size": "5",
                "batch_size_unit": "gal",
                "hops": [
                    {
                        "ingredient_name": "Citra",
                        "amount": "2",
                        "unit": "oz",
                        "alpha_acid": "12",
                        "stage": "DRY_HOP",
                        "time_minutes": 4320,
                    }
                ],
            },
        },
    )
    assert response.status_code == 201
    assert response.json()["version_number"] == 2


@patch("app.api.v1.recipes.recipe_service.activate_version", new_callable=AsyncMock)
def test_activate_version_api(mock_activate):
    mock_activate.return_value = _version(status="ACTIVE")
    response = client.post(
        "/api/v1/recipe-versions/eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee/activate"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
