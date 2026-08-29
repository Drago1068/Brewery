import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CanonicalUnit = Literal["g", "L", "each"]
IngredientCategory = Literal[
    "FERMENTABLE",
    "HOP",
    "YEAST",
    "WATER_ADDITION",
    "ADJUNCT",
    "FINING",
    "NUTRIENT",
    "MISCELLANEOUS",
]


class EquipmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    default_batch_liters: Decimal = Field(gt=0, le=100000)
    preferred_volume_unit: Literal["L", "gal"] = "L"
    preferred_temperature_unit: Literal["degC", "degF"] = "degC"
    brewhouse_efficiency: Decimal = Field(gt=0, le=1)
    mash_efficiency: Decimal | None = Field(default=None, gt=0, le=1)
    boil_off_liters_per_hour: Decimal = Field(ge=0, le=10000)
    kettle_loss_liters: Decimal = Field(default=0, ge=0)
    mash_tun_deadspace_liters: Decimal = Field(default=0, ge=0)
    fermenter_loss_liters: Decimal = Field(default=0, ge=0)
    packaging_loss_liters: Decimal = Field(default=0, ge=0)
    grain_absorption_liters_per_kg: Decimal = Field(default=Decimal("0.8"), ge=0)
    hop_absorption_liters_per_kg: Decimal = Field(default=Decimal("8.0"), ge=0)


class EquipmentResponse(EquipmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class IngredientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    category: IngredientCategory
    manufacturer: str | None = Field(default=None, max_length=180)
    canonical_unit: CanonicalUnit
    attributes: dict = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_category_attributes(self):
        if self.category == "FERMENTABLE":
            potential = self.attributes.get("potential_ppg")
            if potential is None or not 1 <= Decimal(str(potential)) <= 60:
                raise ValueError("Fermentables require potential_ppg between 1 and 60")
        if self.category == "HOP":
            alpha = self.attributes.get("alpha_acid_percent")
            if alpha is None or not 0 <= Decimal(str(alpha)) <= 100:
                raise ValueError("Hops require alpha_acid_percent between 0 and 100")
        return self


class IngredientResponse(IngredientCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    notes: str | None = Field(default=None, max_length=4000)


class SupplierResponse(SupplierCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class SupplierItemCreate(BaseModel):
    ingredient_id: uuid.UUID
    sku: str = Field(min_length=1, max_length=120)
    package_quantity: Decimal | None = Field(default=None, gt=0)
    unit: CanonicalUnit | None = None
    unit_cost: Decimal | None = Field(default=None, ge=0)


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class LocationResponse(LocationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class IngredientLotCreate(BaseModel):
    ingredient_id: uuid.UUID
    lot_code: str = Field(min_length=1, max_length=160)
    supplier_id: uuid.UUID | None = None
    purchase_date: date | None = None
    received_quantity: Decimal = Field(gt=0)
    unit: CanonicalUnit
    cost: Decimal | None = Field(default=None, ge=0)
    best_by_date: date | None = None
    hop_alpha_acid_percent: Decimal | None = Field(default=None, ge=0, le=100)
    yeast_manufactured_date: date | None = None
    yeast_expiration_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    location_id: uuid.UUID | None = None


class IngredientLotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    ingredient_id: uuid.UUID
    lot_code: str
    received_quantity: Decimal
    unit: str
    hop_alpha_acid_percent: Decimal | None


class InventoryTransactionCreate(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_lot_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    destination_location_id: uuid.UUID | None = None
    transaction_type: Literal[
        "PURCHASE", "ADJUSTMENT", "CONSUMPTION", "WASTE", "TRANSFER", "RETURN"
    ]
    quantity: Decimal
    unit: CanonicalUnit
    reference_type: str | None = Field(default=None, max_length=80)
    reference_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_shape(self):
        if self.transaction_type == "ADJUSTMENT" and self.quantity == 0:
            raise ValueError("An adjustment must be non-zero")
        if self.transaction_type != "ADJUSTMENT" and self.quantity <= 0:
            raise ValueError("Transaction quantity must be positive")
        if self.transaction_type == "TRANSFER":
            if not self.location_id or not self.destination_location_id:
                raise ValueError("Transfers require source and destination locations")
            if self.location_id == self.destination_location_id:
                raise ValueError("Transfer locations must differ")
        elif self.destination_location_id is not None:
            raise ValueError("Destination is only valid for transfers")
        return self


class ReservationCreate(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_lot_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    recipe_version_id: uuid.UUID | None = None
    quantity: Decimal = Field(gt=0)
    unit: CanonicalUnit


class SafetyStockCreate(BaseModel):
    ingredient_id: uuid.UUID
    threshold_quantity: Decimal = Field(ge=0)
    unit: CanonicalUnit
    enabled: bool = True


class InventoryBalanceResponse(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    on_hand: Decimal
    reserved: Decimal
    available: Decimal
    safety_stock_threshold: Decimal | None
    state: Literal["OK", "BELOW_SAFETY_STOCK", "SHORTAGE"]


class RecipeIngredientInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ingredient_id: uuid.UUID
    ingredient_lot_id: uuid.UUID | None = None
    amount: Decimal = Field(gt=0)
    unit: CanonicalUnit
    use_stage: Literal[
        "MASH",
        "FIRST_WORT",
        "BOIL",
        "WHIRLPOOL",
        "DRY_HOP",
        "FERMENTATION",
        "PACKAGING",
        "MISCELLANEOUS",
    ]
    timing_minutes: int | None = Field(default=None, ge=0, le=10080)
    percentage: Decimal | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=2000)


class ProcessStepInput(BaseModel):
    step_type: Literal["MASH", "BOIL", "FERMENTATION_FOUNDATION", "PACKAGING_FOUNDATION"]
    sequence: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=160)
    duration_minutes: int | None = Field(default=None, ge=0)
    temperature_c: Decimal | None = None
    details: dict = Field(default_factory=dict)


class WaterProfileInput(BaseModel):
    calcium_ppm: Decimal | None = Field(default=None, ge=0)
    magnesium_ppm: Decimal | None = Field(default=None, ge=0)
    sodium_ppm: Decimal | None = Field(default=None, ge=0)
    chloride_ppm: Decimal | None = Field(default=None, ge=0)
    sulfate_ppm: Decimal | None = Field(default=None, ge=0)
    bicarbonate_ppm: Decimal | None = Field(default=None, ge=0)


class RecipeDesignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    equipment_profile_id: uuid.UUID
    batch_size_liters: Decimal = Field(gt=0)
    style_name: str | None = Field(default=None, max_length=160)
    bjcp_category: str | None = Field(default=None, max_length=80)
    target_mash_temperature_c: Decimal = Field(default=Decimal("66.67"), ge=0, le=100)
    target_mash_ph: Decimal = Field(default=Decimal("5.30"), ge=0, le=14)
    mash_ph_tolerance: Decimal = Field(default=Decimal("0.05"), ge=0, le=2)
    planned_mash_duration_minutes: int = Field(default=60, ge=1, le=240)
    boil_duration_minutes: int = Field(default=60, ge=0, le=360)
    apparent_attenuation: Decimal = Field(default=Decimal("0.75"), ge=0, le=1)
    target_carbonation_volumes: Decimal = Field(default=Decimal("2.4"), ge=0, le=6)
    mash_ratio_liters_per_kg: Decimal = Field(default=Decimal("2.7"), gt=0)
    grain_temperature_c: Decimal = Field(default=Decimal("20"), ge=-20, le=60)
    ingredients: list[RecipeIngredientInput] = Field(min_length=1)
    process_steps: list[ProcessStepInput] = Field(default_factory=list)
    water_profile: WaterProfileInput | None = None
    notes: str | None = Field(default=None, max_length=4000)


class RecipeScaleRequest(BaseModel):
    target_batch_liters: Decimal = Field(gt=0)
    target_equipment_profile_id: uuid.UUID | None = None


class AvailabilityLine(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    required: Decimal
    on_hand: Decimal
    reserved: Decimal
    available: Decimal
    shortage: Decimal
    status: Literal["AVAILABLE", "PARTIAL", "SHORTAGE"]


class RecipeDesignResponse(BaseModel):
    recipe_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    name: str
    batch_size_liters: Decimal
    equipment_profile_id: uuid.UUID
    calculations: dict
    ingredients: list[RecipeIngredientInput]
    availability: list[AvailabilityLine]


class SubstitutionCreate(BaseModel):
    original_ingredient_id: uuid.UUID
    substitute_ingredient_id: uuid.UUID
    conversion_ratio: Decimal = Field(gt=0)
    process_impact: str = Field(min_length=1, max_length=2000)
    flavor_impact: str = Field(min_length=1, max_length=2000)
    confidence: Decimal = Field(ge=0, le=1)
    requires_brewer_approval: bool = True
