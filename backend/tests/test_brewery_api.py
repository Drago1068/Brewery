from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.db.models import Brewery, EquipmentProfile
from app.main import app

client = TestClient(app)


def _brewery(**overrides) -> Brewery:
    data = {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Nazario Home",
        "preferred_units": "US",
        "timezone": "America/New_York",
        "default_batch_size": Decimal("5"),
        "default_batch_size_unit": "gal",
        "default_brewhouse_efficiency": Decimal("72"),
        "created_by": "local-brewer",
        "updated_by": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return Brewery(**data)


def _equipment(**overrides) -> EquipmentProfile:
    data = {
        "id": "22222222-2222-2222-2222-222222222222",
        "brewery_id": "11111111-1111-1111-1111-111111111111",
        "name": "BIAB Setup",
        "system_type": "BIAB",
        "target_batch_size": Decimal("5"),
        "target_batch_size_unit": "gal",
        "kettle_capacity": Decimal("10"),
        "kettle_capacity_unit": "gal",
        "mash_capacity": Decimal("10"),
        "mash_capacity_unit": "gal",
        "boil_off_rate": Decimal("0.75"),
        "boil_off_rate_unit": "gal/hr",
        "trub_loss": Decimal("0.25"),
        "trub_loss_unit": "gal",
        "fermenter_loss": Decimal("0.25"),
        "fermenter_loss_unit": "gal",
        "typical_brewhouse_efficiency": Decimal("70"),
        "notes": None,
        "active": True,
        "created_by": "local-brewer",
        "updated_by": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return EquipmentProfile(**data)


def test_health_reports_increment_5():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["increment"] == 5


@patch("app.api.v1.brewery.brewery_service.get_primary_brewery", new_callable=AsyncMock)
def test_get_brewery_empty(mock_get):
    mock_get.return_value = None
    response = client.get("/api/v1/brewery")
    assert response.status_code == 200
    assert response.json() is None


@patch("app.api.v1.brewery.brewery_service.create_brewery", new_callable=AsyncMock)
def test_create_brewery(mock_create):
    mock_create.return_value = _brewery()
    response = client.post(
        "/api/v1/brewery",
        json={
            "name": "Nazario Home",
            "preferred_units": "US",
            "timezone": "America/New_York",
            "default_batch_size": "5",
            "default_batch_size_unit": "gal",
            "default_brewhouse_efficiency": "72",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Nazario Home"
    assert body["preferred_units"] == "US"
    mock_create.assert_awaited_once()


@patch("app.api.v1.brewery.brewery_service.update_brewery", new_callable=AsyncMock)
def test_update_brewery(mock_update):
    mock_update.return_value = _brewery(name="Updated Brewery")
    response = client.patch(
        "/api/v1/brewery/11111111-1111-1111-1111-111111111111",
        json={"name": "Updated Brewery"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Brewery"


@patch("app.api.v1.equipment.equipment_service.create_equipment", new_callable=AsyncMock)
def test_create_equipment(mock_create):
    mock_create.return_value = _equipment()
    response = client.post(
        "/api/v1/breweries/11111111-1111-1111-1111-111111111111/equipment",
        json={
            "name": "BIAB Setup",
            "system_type": "BIAB",
            "target_batch_size": "5",
            "target_batch_size_unit": "gal",
            "kettle_capacity": "10",
            "kettle_capacity_unit": "gal",
            "mash_capacity": "10",
            "mash_capacity_unit": "gal",
        },
    )
    assert response.status_code == 201
    assert response.json()["system_type"] == "BIAB"


@patch("app.api.v1.equipment.equipment_service.list_equipment", new_callable=AsyncMock)
def test_list_equipment(mock_list):
    mock_list.return_value = [_equipment()]
    response = client.get(
        "/api/v1/breweries/11111111-1111-1111-1111-111111111111/equipment"
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


@patch("app.api.v1.meta.select")
def test_meta_modules_brewery_active(_mock_select):
    from app.db.session import get_db

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
        assert data["increment"] == 5
        assert data["modules"]["brewery"] == "active"
        assert data["modules"]["equipment"] == "active"
        assert data["modules"]["ingredients"] == "active"
        assert data["modules"]["inventory"] == "active"
        assert data["modules"]["recipes"] == "active"
        assert data["modules"]["calculations"] == "active"
    finally:
        app.dependency_overrides.clear()
