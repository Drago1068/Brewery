import uuid
from collections import defaultdict
from decimal import Decimal

from calculations import (
    abv,
    brewing_water_volumes,
    expected_fg,
    expected_og,
    fermentable_gravity_points,
    morey_srm,
    priming_sugar_grams,
    recipe_scaling_factors,
    scale_quantity,
    strike_temperature_c,
    tinseth_ibu,
    yeast_pitch_cells,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit
from brewing_api.domain.equipment.models import EquipmentProfile
from brewing_api.domain.identity.models import User
from brewing_api.domain.ingredients.models import (
    Ingredient,
    IngredientLot,
    Supplier,
    SupplierItem,
)
from brewing_api.domain.inventory.models import (
    InventoryLocation,
    InventoryReservation,
    InventoryTransaction,
    SafetyStockPolicy,
)
from brewing_api.domain.recipes.models import (
    IngredientSubstitution,
    Recipe,
    RecipeIngredient,
    RecipeProcessStep,
    RecipeVersion,
    WaterProfileTarget,
)
from brewing_api.platform.time import utc_now


def _owned(db: Session, model, owner_id: uuid.UUID, entity_id: uuid.UUID, label: str):
    entity = db.scalar(select(model).where(model.id == entity_id, model.owner_id == owner_id))
    if entity is None:
        raise NotFoundError(f"{label} not found")
    return entity


def create_equipment(db: Session, user: User, command) -> EquipmentProfile:
    equipment = EquipmentProfile(owner_id=user.id, **command.model_dump())
    db.add(equipment)
    db.flush()
    audit(db, user.id, "EQUIPMENT_CREATED", "EquipmentProfile", equipment.id)
    db.commit()
    db.refresh(equipment)
    return equipment


def list_equipment(db: Session, user: User) -> list[EquipmentProfile]:
    return list(db.scalars(select(EquipmentProfile).where(EquipmentProfile.owner_id == user.id)))


def create_ingredient(db: Session, user: User, command) -> Ingredient:
    ingredient = Ingredient(owner_id=user.id, **command.model_dump())
    db.add(ingredient)
    db.flush()
    audit(db, user.id, "INGREDIENT_CREATED", "Ingredient", ingredient.id)
    db.commit()
    db.refresh(ingredient)
    return ingredient


def list_ingredients(db: Session, user: User) -> list[Ingredient]:
    return list(
        db.scalars(
            select(Ingredient)
            .where(Ingredient.owner_id == user.id)
            .order_by(Ingredient.category, Ingredient.name)
        )
    )


def create_supplier(db: Session, user: User, command) -> Supplier:
    supplier = Supplier(owner_id=user.id, **command.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def list_suppliers(db: Session, user: User) -> list[Supplier]:
    return list(db.scalars(select(Supplier).where(Supplier.owner_id == user.id)))


def create_supplier_item(db: Session, user: User, supplier_id: uuid.UUID, command) -> SupplierItem:
    _owned(db, Supplier, user.id, supplier_id, "Supplier")
    ingredient = _owned(db, Ingredient, user.id, command.ingredient_id, "Ingredient")
    if command.unit and command.unit != ingredient.canonical_unit:
        raise DomainError(f"Ingredient requires canonical unit {ingredient.canonical_unit}")
    item = SupplierItem(supplier_id=supplier_id, **command.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_location(db: Session, user: User, command) -> InventoryLocation:
    location = InventoryLocation(owner_id=user.id, **command.model_dump())
    db.add(location)
    db.flush()
    audit(db, user.id, "INVENTORY_LOCATION_CREATED", "InventoryLocation", location.id)
    db.commit()
    db.refresh(location)
    return location


def list_locations(db: Session, user: User) -> list[InventoryLocation]:
    return list(db.scalars(select(InventoryLocation).where(InventoryLocation.owner_id == user.id)))


def _ingredient_and_unit(
    db: Session, user: User, ingredient_id: uuid.UUID, unit: str
) -> Ingredient:
    ingredient = _owned(db, Ingredient, user.id, ingredient_id, "Ingredient")
    if ingredient.canonical_unit != unit:
        raise DomainError(f"Ingredient requires canonical unit {ingredient.canonical_unit}")
    return ingredient


def _validate_location(db: Session, user: User, location_id: uuid.UUID | None) -> None:
    if location_id:
        _owned(db, InventoryLocation, user.id, location_id, "Inventory location")


def create_lot(db: Session, user: User, command) -> IngredientLot:
    ingredient = _ingredient_and_unit(db, user, command.ingredient_id, command.unit)
    if command.location_id:
        _validate_location(db, user, command.location_id)
    if command.hop_alpha_acid_percent is not None and ingredient.category != "HOP":
        raise DomainError("Lot alpha acid is only valid for hops")
    values = command.model_dump(exclude={"location_id"})
    lot = IngredientLot(owner_id=user.id, **values)
    db.add(lot)
    db.flush()
    transaction = InventoryTransaction(
        owner_id=user.id,
        ingredient_id=ingredient.id,
        ingredient_lot_id=lot.id,
        location_id=command.location_id,
        transaction_type="PURCHASE",
        quantity=command.received_quantity,
        unit=command.unit,
        reference_type="IngredientLot",
        reference_id=lot.id,
        note="Initial lot receipt",
    )
    db.add(transaction)
    audit(db, user.id, "INGREDIENT_LOT_RECEIVED", "IngredientLot", lot.id)
    db.commit()
    db.refresh(lot)
    return lot


def list_lots(db: Session, user: User) -> list[IngredientLot]:
    return list(db.scalars(select(IngredientLot).where(IngredientLot.owner_id == user.id)))


def _validate_lot(
    db: Session,
    user: User,
    ingredient_id: uuid.UUID,
    lot_id: uuid.UUID | None,
) -> None:
    if lot_id is None:
        return
    lot = _owned(db, IngredientLot, user.id, lot_id, "Ingredient lot")
    if lot.ingredient_id != ingredient_id:
        raise DomainError("Ingredient lot does not belong to the selected ingredient")


def _physical_delta(transaction_type: str, quantity: Decimal) -> Decimal:
    if transaction_type in {"PURCHASE", "RETURN"}:
        return quantity
    if transaction_type in {"CONSUMPTION", "WASTE"}:
        return -quantity
    if transaction_type == "ADJUSTMENT":
        return quantity
    return Decimal("0")


def balance(
    db: Session,
    user: User,
    ingredient_id: uuid.UUID,
    lot_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    query = select(InventoryTransaction).where(
        InventoryTransaction.owner_id == user.id,
        InventoryTransaction.ingredient_id == ingredient_id,
    )
    if lot_id:
        query = query.where(InventoryTransaction.ingredient_lot_id == lot_id)
    transactions = list(db.scalars(query))
    on_hand = Decimal("0")
    for transaction in transactions:
        if transaction.transaction_type == "TRANSFER":
            if location_id is None:
                continue
            if transaction.location_id == location_id:
                on_hand -= transaction.quantity
            if transaction.destination_location_id == location_id:
                on_hand += transaction.quantity
        elif location_id is None or transaction.location_id == location_id:
            on_hand += _physical_delta(transaction.transaction_type, transaction.quantity)
    reservation_query = select(func.coalesce(func.sum(InventoryReservation.quantity), 0)).where(
        InventoryReservation.owner_id == user.id,
        InventoryReservation.ingredient_id == ingredient_id,
        InventoryReservation.status == "ACTIVE",
    )
    if lot_id:
        reservation_query = reservation_query.where(
            InventoryReservation.ingredient_lot_id == lot_id
        )
    if location_id:
        reservation_query = reservation_query.where(InventoryReservation.location_id == location_id)
    reserved = Decimal(db.scalar(reservation_query) or 0)
    return on_hand, reserved, on_hand - reserved


def record_transaction(db: Session, user: User, command) -> InventoryTransaction:
    _ingredient_and_unit(db, user, command.ingredient_id, command.unit)
    _validate_lot(db, user, command.ingredient_id, command.ingredient_lot_id)
    _validate_location(db, user, command.location_id)
    _validate_location(db, user, command.destination_location_id)
    _, _, available = balance(
        db, user, command.ingredient_id, command.ingredient_lot_id, command.location_id
    )
    debit = (
        command.quantity
        if command.transaction_type in {"CONSUMPTION", "WASTE", "TRANSFER"}
        else max(Decimal("0"), -command.quantity)
    )
    if debit > available:
        raise ConflictError("Transaction would make available inventory negative")
    transaction = InventoryTransaction(owner_id=user.id, **command.model_dump())
    db.add(transaction)
    db.flush()
    audit(db, user.id, "INVENTORY_TRANSACTION_RECORDED", "InventoryTransaction", transaction.id)
    db.commit()
    db.refresh(transaction)
    return transaction


def create_reservation(db: Session, user: User, command) -> InventoryReservation:
    _ingredient_and_unit(db, user, command.ingredient_id, command.unit)
    _validate_lot(db, user, command.ingredient_id, command.ingredient_lot_id)
    _validate_location(db, user, command.location_id)
    if command.recipe_version_id:
        get_owned_version(db, user, command.recipe_version_id)
    _, _, available = balance(
        db, user, command.ingredient_id, command.ingredient_lot_id, command.location_id
    )
    if command.quantity > available:
        raise ConflictError("Reservation exceeds available inventory")
    reservation = InventoryReservation(owner_id=user.id, status="ACTIVE", **command.model_dump())
    db.add(reservation)
    db.flush()
    db.add(
        InventoryTransaction(
            owner_id=user.id,
            ingredient_id=command.ingredient_id,
            ingredient_lot_id=command.ingredient_lot_id,
            location_id=command.location_id,
            transaction_type="RESERVATION",
            quantity=command.quantity,
            unit=command.unit,
            reference_type="InventoryReservation",
            reference_id=reservation.id,
        )
    )
    audit(db, user.id, "INVENTORY_RESERVED", "InventoryReservation", reservation.id)
    db.commit()
    db.refresh(reservation)
    return reservation


def release_reservation(db: Session, user: User, reservation_id: uuid.UUID) -> InventoryReservation:
    reservation = _owned(db, InventoryReservation, user.id, reservation_id, "Inventory reservation")
    if reservation.status != "ACTIVE":
        raise ConflictError("Only active reservations can be released")
    reservation.status = "RELEASED"
    reservation.released_at = utc_now()
    db.add(
        InventoryTransaction(
            owner_id=user.id,
            ingredient_id=reservation.ingredient_id,
            ingredient_lot_id=reservation.ingredient_lot_id,
            location_id=reservation.location_id,
            transaction_type="RELEASE",
            quantity=reservation.quantity,
            unit=reservation.unit,
            reference_type="InventoryReservation",
            reference_id=reservation.id,
        )
    )
    audit(db, user.id, "INVENTORY_RESERVATION_RELEASED", "InventoryReservation", reservation.id)
    db.commit()
    db.refresh(reservation)
    return reservation


def set_safety_stock(db: Session, user: User, command) -> SafetyStockPolicy:
    _ingredient_and_unit(db, user, command.ingredient_id, command.unit)
    policy = db.scalar(
        select(SafetyStockPolicy).where(SafetyStockPolicy.ingredient_id == command.ingredient_id)
    )
    if policy and policy.owner_id != user.id:
        raise NotFoundError("Ingredient not found")
    if policy is None:
        policy = SafetyStockPolicy(owner_id=user.id, **command.model_dump())
        db.add(policy)
    else:
        policy.threshold_quantity = command.threshold_quantity
        policy.enabled = command.enabled
    db.commit()
    db.refresh(policy)
    return policy


def inventory_balances(db: Session, user: User) -> list[dict]:
    results = []
    for ingredient in list_ingredients(db, user):
        on_hand, reserved, available = balance(db, user, ingredient.id)
        policy = db.scalar(
            select(SafetyStockPolicy).where(
                SafetyStockPolicy.ingredient_id == ingredient.id,
                SafetyStockPolicy.owner_id == user.id,
            )
        )
        threshold = policy.threshold_quantity if policy and policy.enabled else None
        state = "SHORTAGE" if available < 0 else "OK"
        if state == "OK" and threshold is not None and available < threshold:
            state = "BELOW_SAFETY_STOCK"
        results.append(
            {
                "ingredient_id": ingredient.id,
                "ingredient_name": ingredient.name,
                "unit": ingredient.canonical_unit,
                "on_hand": on_hand,
                "reserved": reserved,
                "available": available,
                "safety_stock_threshold": threshold,
                "state": state,
            }
        )
    return results


def get_owned_version(db: Session, user: User, version_id: uuid.UUID) -> RecipeVersion:
    version = db.scalar(
        select(RecipeVersion)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .where(RecipeVersion.id == version_id, Recipe.owner_id == user.id)
    )
    if version is None:
        raise NotFoundError("Recipe version not found")
    return version


def _json_decimal(value) -> str:
    return format(Decimal(value), "f")


def _equipment_snapshot(equipment: EquipmentProfile) -> dict:
    fields = (
        "id",
        "name",
        "default_batch_liters",
        "brewhouse_efficiency",
        "mash_efficiency",
        "boil_off_liters_per_hour",
        "kettle_loss_liters",
        "mash_tun_deadspace_liters",
        "fermenter_loss_liters",
        "packaging_loss_liters",
        "grain_absorption_liters_per_kg",
        "hop_absorption_liters_per_kg",
    )
    return {field: str(getattr(equipment, field)) for field in fields}


def _calculate(
    ingredients: list[tuple[object, Ingredient, IngredientLot | None]],
    equipment: EquipmentProfile,
    batch_liters: Decimal,
    boil_minutes: int,
    attenuation: Decimal,
    mash_ratio: Decimal,
    grain_temperature_c: Decimal,
    mash_temperature_c: Decimal,
    carbonation_volumes: Decimal,
) -> tuple[dict, dict]:
    fermentables = []
    grain_kg = Decimal("0")
    yeast_count = Decimal("0")
    for line, ingredient, _lot in ingredients:
        if ingredient.category == "FERMENTABLE":
            potential = Decimal(str(ingredient.attributes["potential_ppg"]))
            fermentables.append(
                fermentable_gravity_points(
                    potential, line.amount, batch_liters, equipment.brewhouse_efficiency
                )
            )
            grain_kg += line.amount / Decimal("1000")
        elif ingredient.category == "YEAST":
            yeast_count += line.amount
    if not fermentables:
        raise DomainError("A recipe requires at least one fermentable")
    og = expected_og(fermentables)
    fg = expected_fg(og, attenuation)
    ibu = Decimal("0")
    colors = []
    for line, ingredient, lot in ingredients:
        if ingredient.category == "HOP" and line.use_stage in {"BOIL", "FIRST_WORT"}:
            alpha = (
                lot.hop_alpha_acid_percent
                if lot and lot.hop_alpha_acid_percent is not None
                else Decimal(str(ingredient.attributes["alpha_acid_percent"]))
            )
            ibu += tinseth_ibu(
                line.amount, alpha, Decimal(line.timing_minutes or 0), og, batch_liters
            )
        if ingredient.category == "FERMENTABLE":
            colors.append(
                (line.amount, Decimal(str(ingredient.attributes.get("color_lovibond", 0))))
            )
    water = brewing_water_volumes(
        grain_kg,
        batch_liters,
        mash_ratio,
        Decimal(boil_minutes),
        equipment.boil_off_liters_per_hour,
        equipment.grain_absorption_liters_per_kg,
        equipment.mash_tun_deadspace_liters,
        equipment.kettle_loss_liters,
        equipment.fermenter_loss_liters,
        equipment.packaging_loss_liters,
    )
    pitch = yeast_pitch_cells(batch_liters, og, Decimal("0.75"))
    outputs = {
        "og": _json_decimal(og),
        "fg_estimate": _json_decimal(fg),
        "abv_percent_estimate": _json_decimal(abv(og, fg)),
        "ibu_estimate": _json_decimal(ibu),
        "color_srm_estimate": _json_decimal(morey_srm(colors, batch_liters)),
        "apparent_attenuation_assumption": _json_decimal(attenuation),
        "brewhouse_efficiency_assumption": _json_decimal(equipment.brewhouse_efficiency),
        "batch_liters": _json_decimal(batch_liters),
        "strike_liters": _json_decimal(water.strike_liters),
        "sparge_liters": _json_decimal(water.sparge_liters),
        "total_liquor_liters": _json_decimal(water.total_liquor_liters),
        "pre_boil_liters": _json_decimal(water.pre_boil_liters),
        "post_boil_liters": _json_decimal(water.post_boil_liters),
        "strike_temperature_c": _json_decimal(
            strike_temperature_c(mash_temperature_c, grain_temperature_c, mash_ratio)
        ),
        "yeast_pitch_cells_estimate": _json_decimal(pitch),
        "yeast_units_entered": _json_decimal(yeast_count),
        "priming_sugar_grams_estimate": _json_decimal(
            priming_sugar_grams(batch_liters, carbonation_volumes, Decimal("20"))
        ),
        "fermentable_grams": _json_decimal(grain_kg * Decimal("1000")),
    }
    inputs = {
        "batch_liters": _json_decimal(batch_liters),
        "boil_minutes": boil_minutes,
        "attenuation": _json_decimal(attenuation),
        "mash_ratio_liters_per_kg": _json_decimal(mash_ratio),
        "grain_temperature_c": _json_decimal(grain_temperature_c),
        "mash_temperature_c": _json_decimal(mash_temperature_c),
        "carbonation_volumes": _json_decimal(carbonation_volumes),
        "pitch_rate_million_per_ml_plato": _json_decimal(Decimal("0.75")),
    }
    return inputs, outputs


def _availability(db: Session, user: User, lines: list[RecipeIngredient]) -> list[dict]:
    required = defaultdict(Decimal)
    for line in lines:
        required[(line.ingredient_id, line.unit)] += line.amount
    response = []
    for (ingredient_id, unit), amount in required.items():
        ingredient = _owned(db, Ingredient, user.id, ingredient_id, "Ingredient")
        on_hand, reserved, available = balance(db, user, ingredient_id)
        shortage = max(Decimal("0"), amount - available)
        status = "AVAILABLE" if shortage == 0 else ("PARTIAL" if available > 0 else "SHORTAGE")
        response.append(
            {
                "ingredient_id": ingredient_id,
                "ingredient_name": ingredient.name,
                "unit": unit,
                "required": amount,
                "on_hand": on_hand,
                "reserved": reserved,
                "available": available,
                "shortage": shortage,
                "status": status,
            }
        )
    return response


def _response(db: Session, user: User, recipe: Recipe, version: RecipeVersion) -> dict:
    lines = list(
        db.scalars(select(RecipeIngredient).where(RecipeIngredient.recipe_version_id == version.id))
    )
    return {
        "recipe_id": recipe.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "name": recipe.name,
        "batch_size_liters": version.batch_size_liters,
        "equipment_profile_id": version.equipment_profile_id,
        "calculations": version.calculation_outputs or {},
        "ingredients": lines,
        "availability": _availability(db, user, lines),
    }


def create_recipe_design(db: Session, user: User, command) -> dict:
    equipment = _owned(
        db, EquipmentProfile, user.id, command.equipment_profile_id, "Equipment profile"
    )
    resolved = []
    for line in command.ingredients:
        ingredient = _ingredient_and_unit(db, user, line.ingredient_id, line.unit)
        _validate_lot(db, user, line.ingredient_id, line.ingredient_lot_id)
        lot = db.get(IngredientLot, line.ingredient_lot_id) if line.ingredient_lot_id else None
        resolved.append((line, ingredient, lot))
    inputs, outputs = _calculate(
        resolved,
        equipment,
        command.batch_size_liters,
        command.boil_duration_minutes,
        command.apparent_attenuation,
        command.mash_ratio_liters_per_kg,
        command.grain_temperature_c,
        command.target_mash_temperature_c,
        command.target_carbonation_volumes,
    )
    recipe = Recipe(owner_id=user.id, name=command.name.strip())
    db.add(recipe)
    db.flush()
    version = RecipeVersion(
        recipe_id=recipe.id,
        version_number=1,
        target_mash_temperature=command.target_mash_temperature_c,
        mash_temperature_unit="degC",
        target_mash_ph=command.target_mash_ph,
        mash_ph_tolerance=command.mash_ph_tolerance,
        target_mash_gravity=Decimal(outputs["og"]),
        mash_gravity_tolerance=Decimal("0.003"),
        planned_mash_duration_minutes=command.planned_mash_duration_minutes,
        equipment_profile_id=equipment.id,
        style_name=command.style_name,
        bjcp_category=command.bjcp_category,
        batch_size_liters=command.batch_size_liters,
        target_og=Decimal(outputs["og"]),
        target_fg=Decimal(outputs["fg_estimate"]),
        target_abv_percent=Decimal(outputs["abv_percent_estimate"]),
        target_ibu=Decimal(outputs["ibu_estimate"]),
        target_color_srm=Decimal(outputs["color_srm_estimate"]),
        target_carbonation_volumes=command.target_carbonation_volumes,
        boil_duration_minutes=command.boil_duration_minutes,
        apparent_attenuation=command.apparent_attenuation,
        equipment_snapshot=_equipment_snapshot(equipment),
        calculation_inputs=inputs,
        calculation_outputs=outputs,
        model_versions={
            "bitterness": "tinseth-v1",
            "color": "morey-v1",
            "abv": "simple-131.25-v1",
            "units": "canonical-si-v1",
        },
        notes=command.notes,
    )
    db.add(version)
    db.flush()
    for line, _ingredient, _lot in resolved:
        db.add(RecipeIngredient(recipe_version_id=version.id, **line.model_dump()))
    for step in command.process_steps:
        db.add(RecipeProcessStep(recipe_version_id=version.id, **step.model_dump()))
    if command.water_profile:
        db.add(
            WaterProfileTarget(recipe_version_id=version.id, **command.water_profile.model_dump())
        )
    audit(db, user.id, "RECIPE_VERSION_CREATED", "RecipeVersion", version.id, {"version_number": 1})
    db.commit()
    return _response(db, user, recipe, version)


def get_recipe_design(db: Session, user: User, version_id: uuid.UUID) -> dict:
    version = get_owned_version(db, user, version_id)
    recipe = db.get(Recipe, version.recipe_id)
    return _response(db, user, recipe, version)


def clone_recipe_version(db: Session, user: User, version_id: uuid.UUID, command) -> dict:
    source = get_owned_version(db, user, version_id)
    recipe = db.get(Recipe, source.recipe_id)
    target_equipment_id = command.target_equipment_profile_id or source.equipment_profile_id
    equipment = _owned(db, EquipmentProfile, user.id, target_equipment_id, "Equipment profile")
    source_lines = list(
        db.scalars(select(RecipeIngredient).where(RecipeIngredient.recipe_version_id == source.id))
    )
    source_inputs = source.calculation_inputs or {}
    source_liquor = Decimal((source.calculation_outputs or {})["total_liquor_liters"])
    grain_kg = sum(
        (
            line.amount
            for line in source_lines
            if db.get(Ingredient, line.ingredient_id).category == "FERMENTABLE"
        ),
        Decimal("0"),
    ) / Decimal("1000")
    target_water = brewing_water_volumes(
        grain_kg * command.target_batch_liters / source.batch_size_liters,
        command.target_batch_liters,
        Decimal(source_inputs["mash_ratio_liters_per_kg"]),
        Decimal(source.boil_duration_minutes),
        equipment.boil_off_liters_per_hour,
        equipment.grain_absorption_liters_per_kg,
        equipment.mash_tun_deadspace_liters,
        equipment.kettle_loss_liters,
        equipment.fermenter_loss_liters,
        equipment.packaging_loss_liters,
    )
    factors = recipe_scaling_factors(
        source.batch_size_liters,
        command.target_batch_liters,
        Decimal(source.equipment_snapshot["brewhouse_efficiency"]),
        equipment.brewhouse_efficiency,
        source_liquor,
        target_water.total_liquor_liters,
    )
    scaled = []
    for line in source_lines:
        ingredient = _owned(db, Ingredient, user.id, line.ingredient_id, "Ingredient")
        factor = factors.volume
        if ingredient.category == "FERMENTABLE":
            factor = factors.fermentable
        elif ingredient.category == "HOP":
            factor = factors.hop
        elif ingredient.category == "YEAST":
            factor = factors.yeast
        elif ingredient.category == "WATER_ADDITION":
            factor = factors.salt
        clone_line = type("Line", (), {})()
        for field in (
            "ingredient_id",
            "ingredient_lot_id",
            "unit",
            "use_stage",
            "timing_minutes",
            "percentage",
            "notes",
        ):
            setattr(clone_line, field, getattr(line, field))
        clone_line.amount = scale_quantity(line.amount, factor)
        lot = db.get(IngredientLot, line.ingredient_lot_id) if line.ingredient_lot_id else None
        scaled.append((clone_line, ingredient, lot))
    inputs, outputs = _calculate(
        scaled,
        equipment,
        command.target_batch_liters,
        source.boil_duration_minutes,
        source.apparent_attenuation,
        Decimal(source_inputs["mash_ratio_liters_per_kg"]),
        Decimal(source_inputs["grain_temperature_c"]),
        Decimal(source_inputs["mash_temperature_c"]),
        source.target_carbonation_volumes,
    )
    version_number = (
        db.scalar(
            select(func.max(RecipeVersion.version_number)).where(
                RecipeVersion.recipe_id == recipe.id
            )
        )
        + 1
    )
    version = RecipeVersion(
        recipe_id=recipe.id,
        version_number=version_number,
        target_mash_temperature=source.target_mash_temperature,
        mash_temperature_unit=source.mash_temperature_unit,
        target_mash_ph=source.target_mash_ph,
        mash_ph_tolerance=source.mash_ph_tolerance,
        target_mash_gravity=Decimal(outputs["og"]),
        mash_gravity_tolerance=source.mash_gravity_tolerance,
        planned_mash_duration_minutes=source.planned_mash_duration_minutes,
        equipment_profile_id=equipment.id,
        style_name=source.style_name,
        bjcp_category=source.bjcp_category,
        batch_size_liters=command.target_batch_liters,
        target_og=Decimal(outputs["og"]),
        target_fg=Decimal(outputs["fg_estimate"]),
        target_abv_percent=Decimal(outputs["abv_percent_estimate"]),
        target_ibu=Decimal(outputs["ibu_estimate"]),
        target_color_srm=Decimal(outputs["color_srm_estimate"]),
        target_carbonation_volumes=source.target_carbonation_volumes,
        boil_duration_minutes=source.boil_duration_minutes,
        apparent_attenuation=source.apparent_attenuation,
        equipment_snapshot=_equipment_snapshot(equipment),
        calculation_inputs=inputs,
        calculation_outputs=outputs,
        model_versions=source.model_versions,
        notes=source.notes,
    )
    db.add(version)
    db.flush()
    for line, _ingredient, _lot in scaled:
        db.add(
            RecipeIngredient(
                recipe_version_id=version.id,
                ingredient_id=line.ingredient_id,
                ingredient_lot_id=line.ingredient_lot_id,
                amount=line.amount,
                unit=line.unit,
                use_stage=line.use_stage,
                timing_minutes=line.timing_minutes,
                percentage=line.percentage,
                notes=line.notes,
            )
        )
    source_steps = list(
        db.scalars(
            select(RecipeProcessStep).where(RecipeProcessStep.recipe_version_id == source.id)
        )
    )
    for step in source_steps:
        db.add(
            RecipeProcessStep(
                recipe_version_id=version.id,
                step_type=step.step_type,
                sequence=step.sequence,
                name=step.name,
                duration_minutes=step.duration_minutes,
                temperature_c=step.temperature_c,
                details=step.details,
            )
        )
    source_water = db.scalar(
        select(WaterProfileTarget).where(WaterProfileTarget.recipe_version_id == source.id)
    )
    if source_water:
        db.add(
            WaterProfileTarget(
                recipe_version_id=version.id,
                calcium_ppm=source_water.calcium_ppm,
                magnesium_ppm=source_water.magnesium_ppm,
                sodium_ppm=source_water.sodium_ppm,
                chloride_ppm=source_water.chloride_ppm,
                sulfate_ppm=source_water.sulfate_ppm,
                bicarbonate_ppm=source_water.bicarbonate_ppm,
            )
        )
    audit(
        db,
        user.id,
        "RECIPE_VERSION_CLONED",
        "RecipeVersion",
        version.id,
        {"source_version_id": str(source.id)},
    )
    db.commit()
    return _response(db, user, recipe, version)


def create_substitution(db: Session, user: User, command) -> IngredientSubstitution:
    original = _owned(db, Ingredient, user.id, command.original_ingredient_id, "Ingredient")
    substitute = _owned(db, Ingredient, user.id, command.substitute_ingredient_id, "Ingredient")
    if original.category != substitute.category:
        raise DomainError("Substitutions must use the same ingredient category")
    substitution = IngredientSubstitution(owner_id=user.id, **command.model_dump())
    db.add(substitution)
    db.commit()
    db.refresh(substitution)
    return substitution


def substitution_candidates(
    db: Session, user: User, ingredient_id: uuid.UUID, required_quantity: Decimal
) -> list[dict]:
    _owned(db, Ingredient, user.id, ingredient_id, "Ingredient")
    candidates = list(
        db.scalars(
            select(IngredientSubstitution).where(
                IngredientSubstitution.owner_id == user.id,
                IngredientSubstitution.original_ingredient_id == ingredient_id,
            )
        )
    )
    results = []
    for candidate in candidates:
        ingredient = _owned(
            db, Ingredient, user.id, candidate.substitute_ingredient_id, "Ingredient"
        )
        needed = required_quantity * candidate.conversion_ratio
        on_hand, reserved, available = balance(db, user, ingredient.id)
        results.append(
            {
                "original_ingredient_id": ingredient_id,
                "candidate_substitute_id": ingredient.id,
                "candidate_name": ingredient.name,
                "available_quantity": str(available),
                "required_quantity": str(needed),
                "conversion_ratio": str(candidate.conversion_ratio),
                "process_impact": candidate.process_impact,
                "flavor_impact": candidate.flavor_impact,
                "confidence": str(candidate.confidence),
                "requires_brewer_approval": True,
            }
        )
    return results
