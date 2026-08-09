from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db.models import Ingredient, IngredientLot, InventoryTransaction
from app.domain.enums import IngredientCategory, QuantityUnit
from app.main import app
from app.schemas.inventory import IngredientCreate, InventoryReceive

client = TestClient(app)


def test_fermentable_requires_profile():
    with pytest.raises(ValidationError):
        IngredientCreate(
            category=IngredientCategory.FERMENTABLE,
            name="2-Row",
            default_unit=QuantityUnit.LB,
        )


def test_hop_ingredient_schema_ok():
    payload = IngredientCreate(
        category=IngredientCategory.HOP,
        name="Citra",
        default_unit=QuantityUnit.OZ,
        hop_profile={"hop_type": "PELLET", "default_alpha_acid": "12.5"},
    )
    assert payload.hop_profile is not None
    assert payload.hop_profile.default_alpha_acid == Decimal("12.5")


def test_receive_requires_positive_quantity():
    with pytest.raises(ValidationError):
        InventoryReceive(ingredient_id="x", quantity=Decimal("0"), unit=QuantityUnit.LB)


def _ingredient() -> Ingredient:
    return Ingredient(
        id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        brewery_id="11111111-1111-1111-1111-111111111111",
        category="HOP",
        name="Citra",
        manufacturer="Yakima",
        description=None,
        default_unit="oz",
        active=True,
        created_by="local-brewer",
        updated_by=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _lot() -> IngredientLot:
    return IngredientLot(
        id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        brewery_id="11111111-1111-1111-1111-111111111111",
        ingredient_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        supplier="LHBS",
        supplier_lot_number=None,
        manufacturer_lot_number=None,
        received_date=datetime.now(timezone.utc),
        expiration_date=None,
        quantity_received=Decimal("8"),
        unit="oz",
        purchase_cost=None,
        storage_location="Fridge",
        opened_at=None,
        notes=None,
        actual_alpha_acid=Decimal("13.1"),
        quantity_on_hand=Decimal("8"),
        quantity_reserved=Decimal("0"),
        created_by="local-brewer",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _tx() -> InventoryTransaction:
    return InventoryTransaction(
        id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        brewery_id="11111111-1111-1111-1111-111111111111",
        ingredient_lot_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        transaction_type="RECEIPT",
        quantity=Decimal("8"),
        unit="oz",
        occurred_at=datetime.now(timezone.utc),
        reason="Receipt",
        reference_type=None,
        reference_id=None,
        created_by="local-brewer",
        created_at=datetime.now(timezone.utc),
    )


@patch("app.api.v1.ingredients.ingredient_service.create_ingredient", new_callable=AsyncMock)
def test_create_ingredient_api(mock_create):
    mock_create.return_value = _ingredient()
    response = client.post(
        "/api/v1/breweries/11111111-1111-1111-1111-111111111111/ingredients",
        json={
            "category": "HOP",
            "name": "Citra",
            "manufacturer": "Yakima",
            "default_unit": "oz",
            "hop_profile": {"hop_type": "PELLET", "default_alpha_acid": "12.5"},
        },
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Citra"


@patch("app.api.v1.inventory.inventory_service.receive_inventory", new_callable=AsyncMock)
def test_receive_api(mock_receive):
    mock_receive.return_value = (_lot(), _tx())
    response = client.post(
        "/api/v1/breweries/11111111-1111-1111-1111-111111111111/inventory/receive",
        json={
            "ingredient_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "quantity": "8",
            "unit": "oz",
            "storage_location": "Fridge",
            "actual_alpha_acid": "13.1",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert Decimal(str(body["quantity_on_hand"])) == Decimal("8")
    assert body["storage_location"] == "Fridge"


@patch("app.api.v1.inventory.inventory_service.list_availability", new_callable=AsyncMock)
def test_list_inventory_api(mock_list):
    mock_list.return_value = [
        {
            "ingredient_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "name": "Citra",
            "category": "HOP",
            "manufacturer": "Yakima",
            "unit": "oz",
            "quantity_on_hand": Decimal("8"),
            "quantity_reserved": Decimal("0"),
            "quantity_available": Decimal("8"),
            "storage_locations": ["Fridge"],
            "freshness": "UNKNOWN",
            "lot_count": 1,
        }
    ]
    response = client.get("/api/v1/breweries/11111111-1111-1111-1111-111111111111/inventory")
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Citra"
