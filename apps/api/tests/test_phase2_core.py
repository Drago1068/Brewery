from decimal import Decimal

from calculations import tinseth_ibu

from brewing_api.application.auth import password_hash
from brewing_api.domain.identity.models import User
from brewing_api.platform.database import SessionLocal


def equipment_payload(name="Pilot System"):
    return {
        "name": name,
        "default_batch_liters": "20",
        "brewhouse_efficiency": "0.75",
        "boil_off_liters_per_hour": "3",
        "kettle_loss_liters": "1",
        "mash_tun_deadspace_liters": "0.5",
        "fermenter_loss_liters": "1",
        "packaging_loss_liters": "0.5",
    }


def ingredient_payload(name, category, unit, attributes):
    return {
        "name": name,
        "category": category,
        "canonical_unit": unit,
        "attributes": attributes,
    }


def create_foundation(client):
    equipment = client.post("/api/v1/equipment-profiles", json=equipment_payload())
    assert equipment.status_code == 201, equipment.text
    location = client.post("/api/v1/inventory/locations", json={"name": "Grain Room"})
    assert location.status_code == 201
    ingredients = []
    for payload in (
        ingredient_payload(
            "Pale Malt", "FERMENTABLE", "g", {"potential_ppg": "37", "color_lovibond": "2"}
        ),
        ingredient_payload("Cascade", "HOP", "g", {"alpha_acid_percent": "5.5"}),
        ingredient_payload(
            "US-05",
            "YEAST",
            "each",
            {"attenuation_min": "0.73", "attenuation_max": "0.77"},
        ),
    ):
        response = client.post("/api/v1/ingredients", json=payload)
        assert response.status_code == 201, response.text
        ingredients.append(response.json())
    return equipment.json(), location.json(), ingredients


def receive_lot(client, ingredient, location, quantity, lot_code, alpha=None):
    payload = {
        "ingredient_id": ingredient["id"],
        "lot_code": lot_code,
        "received_quantity": str(quantity),
        "unit": ingredient["canonical_unit"],
        "location_id": location["id"],
    }
    if alpha is not None:
        payload["hop_alpha_acid_percent"] = str(alpha)
    response = client.post("/api/v1/ingredient-lots", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_equipment_ingredient_lot_ledger_reservation_and_safety_stock(authenticated_client):
    equipment, location, ingredients = create_foundation(authenticated_client)
    malt = ingredients[0]
    lot = receive_lot(authenticated_client, malt, location, 10000, "MALT-2026")
    balance = authenticated_client.get("/api/v1/inventory/balances").json()[0]
    assert Decimal(balance["on_hand"]) == Decimal("10000")
    assert balance["available"] == balance["on_hand"]

    reservation = authenticated_client.post(
        "/api/v1/inventory/reservations",
        json={
            "ingredient_id": malt["id"],
            "ingredient_lot_id": lot["id"],
            "location_id": location["id"],
            "quantity": "2500",
            "unit": "g",
        },
    )
    assert reservation.status_code == 201, reservation.text
    balance = authenticated_client.get("/api/v1/inventory/balances").json()[0]
    assert Decimal(balance["reserved"]) == Decimal("2500")
    assert Decimal(balance["available"]) == Decimal("7500")

    policy = authenticated_client.put(
        "/api/v1/inventory/safety-stock",
        json={"ingredient_id": malt["id"], "threshold_quantity": "8000", "unit": "g"},
    )
    assert policy.status_code == 200
    balances = authenticated_client.get("/api/v1/inventory/balances").json()
    assert balances[0]["state"] == "BELOW_SAFETY_STOCK"

    release = authenticated_client.post(
        f"/api/v1/inventory/reservations/{reservation.json()['id']}/release"
    )
    assert release.json()["status"] == "RELEASED"
    balances = authenticated_client.get("/api/v1/inventory/balances").json()
    assert Decimal(balances[0]["available"]) == Decimal("10000")
    assert equipment["name"] == "Pilot System"


def test_recipe_calculate_availability_scale_and_clone_preserves_original(authenticated_client):
    equipment, location, ingredients = create_foundation(authenticated_client)
    malt_lot = receive_lot(authenticated_client, ingredients[0], location, 10000, "MALT-A")
    hop_lot = receive_lot(authenticated_client, ingredients[1], location, 200, "HOP-A", "6.2")
    receive_lot(authenticated_client, ingredients[2], location, 2, "YEAST-A")
    recipe_payload = {
        "name": "Phase Two Pale Ale",
        "equipment_profile_id": equipment["id"],
        "batch_size_liters": "20",
        "ingredients": [
            {
                "ingredient_id": ingredients[0]["id"],
                "ingredient_lot_id": malt_lot["id"],
                "amount": "5000",
                "unit": "g",
                "use_stage": "MASH",
            },
            {
                "ingredient_id": ingredients[1]["id"],
                "ingredient_lot_id": hop_lot["id"],
                "amount": "40",
                "unit": "g",
                "use_stage": "BOIL",
                "timing_minutes": 60,
            },
            {
                "ingredient_id": ingredients[2]["id"],
                "amount": "1",
                "unit": "each",
                "use_stage": "FERMENTATION",
            },
        ],
        "process_steps": [
            {
                "step_type": "MASH",
                "sequence": 1,
                "name": "Saccharification",
                "duration_minutes": 60,
                "temperature_c": "66.7",
            },
            {"step_type": "BOIL", "sequence": 2, "name": "Boil", "duration_minutes": 60},
        ],
        "water_profile": {"calcium_ppm": "50", "chloride_ppm": "60", "sulfate_ppm": "90"},
    }
    created = authenticated_client.post("/api/v1/recipe-designs", json=recipe_payload)
    assert created.status_code == 201, created.text
    original = created.json()
    assert Decimal(original["calculations"]["og"]) > Decimal("1.040")
    expected_lot_ibu = tinseth_ibu(
        Decimal("40"),
        Decimal("6.2"),
        Decimal("60"),
        Decimal(original["calculations"]["og"]),
        Decimal("20"),
    )
    assert Decimal(original["calculations"]["ibu_estimate"]) == expected_lot_ibu
    assert all(line["status"] == "AVAILABLE" for line in original["availability"])

    clone = authenticated_client.post(
        f"/api/v1/recipe-designs/{original['version_id']}/clone",
        json={"target_batch_liters": "10"},
    )
    assert clone.status_code == 200, clone.text
    clone_body = clone.json()
    assert clone_body["version_number"] == 2
    assert Decimal(clone_body["batch_size_liters"]) == Decimal("10")
    reread = authenticated_client.get(
        f"/api/v1/recipe-designs/{original['version_id']}"
    ).json()
    assert reread["version_number"] == 1
    assert Decimal(reread["batch_size_liters"]) == Decimal("20")
    assert reread["calculations"] == original["calculations"]


def test_rejects_mixed_units_and_cross_owner_is_not_exposed(authenticated_client):
    _equipment, _location, ingredients = create_foundation(authenticated_client)
    response = authenticated_client.post(
        "/api/v1/inventory/transactions",
        json={
            "ingredient_id": ingredients[0]["id"],
            "transaction_type": "PURCHASE",
            "quantity": "1",
            "unit": "L",
        },
    )
    assert response.status_code == 400
    assert "canonical unit" in response.json()["detail"]


def test_supplier_item_requires_owned_ingredient_and_matching_unit(authenticated_client):
    _equipment, _location, ingredients = create_foundation(authenticated_client)
    supplier = authenticated_client.post(
        "/api/v1/suppliers", json={"name": "Local Homebrew Shop"}
    )
    assert supplier.status_code == 201
    item = authenticated_client.post(
        f"/api/v1/suppliers/{supplier.json()['id']}/items",
        json={
            "ingredient_id": ingredients[0]["id"],
            "sku": "MALT-25KG",
            "package_quantity": "25000",
            "unit": "g",
            "unit_cost": "42.50",
        },
    )
    assert item.status_code == 201, item.text
    mismatch = authenticated_client.post(
        f"/api/v1/suppliers/{supplier.json()['id']}/items",
        json={"ingredient_id": ingredients[0]["id"], "sku": "BAD", "unit": "L"},
    )
    assert mismatch.status_code == 400


def test_equipment_inventory_and_recipe_ownership_boundaries(authenticated_client):
    equipment, _location, ingredients = create_foundation(authenticated_client)
    with SessionLocal() as db:
        db.add(
            User(
                username="other-brewer",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = authenticated_client.post(
        "/api/v1/auth/login",
        json={"username": "other-brewer", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    assert authenticated_client.get("/api/v1/equipment-profiles").json() == []
    assert authenticated_client.get("/api/v1/ingredients").json() == []
    cross_owner_transaction = authenticated_client.post(
        "/api/v1/inventory/transactions",
        json={
            "ingredient_id": ingredients[0]["id"],
            "transaction_type": "PURCHASE",
            "quantity": "100",
            "unit": "g",
        },
    )
    assert cross_owner_transaction.status_code == 404
    cross_owner_recipe = authenticated_client.post(
        "/api/v1/recipe-designs",
        json={
            "name": "Unauthorized Recipe",
            "equipment_profile_id": equipment["id"],
            "batch_size_liters": "20",
            "ingredients": [
                {
                    "ingredient_id": ingredients[0]["id"],
                    "amount": "1000",
                    "unit": "g",
                    "use_stage": "MASH",
                }
            ],
        },
    )
    assert cross_owner_recipe.status_code == 404
