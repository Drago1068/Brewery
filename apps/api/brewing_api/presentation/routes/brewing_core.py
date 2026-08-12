import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status

from brewing_api.application import brewing_core as service
from brewing_api.presentation.dependencies import CurrentUser, Db
from brewing_api.presentation.phase2_schemas import (
    EquipmentCreate,
    EquipmentResponse,
    IngredientCreate,
    IngredientLotCreate,
    IngredientLotResponse,
    IngredientResponse,
    InventoryBalanceResponse,
    InventoryTransactionCreate,
    LocationCreate,
    LocationResponse,
    RecipeDesignCreate,
    RecipeDesignResponse,
    RecipeScaleRequest,
    ReservationCreate,
    SafetyStockCreate,
    SubstitutionCreate,
    SupplierCreate,
    SupplierItemCreate,
    SupplierResponse,
)

router = APIRouter(tags=["brewing-core"])


@router.post("/equipment-profiles", response_model=EquipmentResponse, status_code=201)
def create_equipment(command: EquipmentCreate, db: Db, user: CurrentUser):
    return service.create_equipment(db, user, command)


@router.get("/equipment-profiles", response_model=list[EquipmentResponse])
def list_equipment(db: Db, user: CurrentUser):
    return service.list_equipment(db, user)


@router.post("/ingredients", response_model=IngredientResponse, status_code=201)
def create_ingredient(command: IngredientCreate, db: Db, user: CurrentUser):
    return service.create_ingredient(db, user, command)


@router.get("/ingredients", response_model=list[IngredientResponse])
def list_ingredients(db: Db, user: CurrentUser):
    return service.list_ingredients(db, user)


@router.post("/suppliers", response_model=SupplierResponse, status_code=201)
def create_supplier(command: SupplierCreate, db: Db, user: CurrentUser):
    return service.create_supplier(db, user, command)


@router.get("/suppliers", response_model=list[SupplierResponse])
def list_suppliers(db: Db, user: CurrentUser):
    return service.list_suppliers(db, user)


@router.post("/suppliers/{supplier_id}/items", status_code=201)
def create_supplier_item(
    supplier_id: uuid.UUID, command: SupplierItemCreate, db: Db, user: CurrentUser
):
    item = service.create_supplier_item(db, user, supplier_id, command)
    return {"id": item.id, "sku": item.sku}


@router.post("/inventory/locations", response_model=LocationResponse, status_code=201)
def create_location(command: LocationCreate, db: Db, user: CurrentUser):
    return service.create_location(db, user, command)


@router.get("/inventory/locations", response_model=list[LocationResponse])
def list_locations(db: Db, user: CurrentUser):
    return service.list_locations(db, user)


@router.post("/ingredient-lots", response_model=IngredientLotResponse, status_code=201)
def create_lot(command: IngredientLotCreate, db: Db, user: CurrentUser):
    return service.create_lot(db, user, command)


@router.get("/ingredient-lots", response_model=list[IngredientLotResponse])
def list_lots(db: Db, user: CurrentUser):
    return service.list_lots(db, user)


@router.post("/inventory/transactions", status_code=status.HTTP_201_CREATED)
def record_transaction(command: InventoryTransactionCreate, db: Db, user: CurrentUser):
    transaction = service.record_transaction(db, user, command)
    return {"id": transaction.id, "transaction_type": transaction.transaction_type}


@router.post("/inventory/reservations", status_code=status.HTTP_201_CREATED)
def reserve(command: ReservationCreate, db: Db, user: CurrentUser):
    reservation = service.create_reservation(db, user, command)
    return {"id": reservation.id, "status": reservation.status}


@router.post("/inventory/reservations/{reservation_id}/release")
def release(reservation_id: uuid.UUID, db: Db, user: CurrentUser):
    reservation = service.release_reservation(db, user, reservation_id)
    return {"id": reservation.id, "status": reservation.status}


@router.put("/inventory/safety-stock")
def set_safety_stock(command: SafetyStockCreate, db: Db, user: CurrentUser):
    policy = service.set_safety_stock(db, user, command)
    return {"id": policy.id, "enabled": policy.enabled}


@router.get("/inventory/balances", response_model=list[InventoryBalanceResponse])
def balances(db: Db, user: CurrentUser):
    return service.inventory_balances(db, user)


@router.post("/recipe-designs", response_model=RecipeDesignResponse, status_code=201)
def create_recipe_design(command: RecipeDesignCreate, db: Db, user: CurrentUser):
    return service.create_recipe_design(db, user, command)


@router.get("/recipe-designs/{version_id}", response_model=RecipeDesignResponse)
def get_recipe_design(version_id: uuid.UUID, db: Db, user: CurrentUser):
    return service.get_recipe_design(db, user, version_id)


@router.post("/recipe-designs/{version_id}/clone", response_model=RecipeDesignResponse)
def clone_recipe_design(
    version_id: uuid.UUID, command: RecipeScaleRequest, db: Db, user: CurrentUser
):
    return service.clone_recipe_version(db, user, version_id, command)


@router.post("/ingredient-substitutions", status_code=status.HTTP_201_CREATED)
def create_substitution(command: SubstitutionCreate, db: Db, user: CurrentUser):
    substitution = service.create_substitution(db, user, command)
    return {"id": substitution.id, "requires_brewer_approval": True}


@router.get("/ingredients/{ingredient_id}/substitution-candidates")
def candidates(
    ingredient_id: uuid.UUID,
    db: Db,
    user: CurrentUser,
    required_quantity: Annotated[Decimal, Query(gt=0)],
):
    return service.substitution_candidates(db, user, ingredient_id, required_quantity)
