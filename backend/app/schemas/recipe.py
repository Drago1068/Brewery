"""Recipe / RecipeVersion API schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import HopStage, MashMethod, QuantityUnit, RecipeStatus, RecipeVersionStatus, VolumeUnit


class RecipeIntentIn(BaseModel):
    desired_aroma: Optional[str] = None
    desired_flavor: Optional[str] = None
    desired_bitterness: Optional[str] = None
    desired_sweetness_dryness: Optional[str] = None
    desired_body: Optional[str] = None
    desired_carbonation_impression: Optional[str] = None
    overall_objective: Optional[str] = None


class RecipeIntentRead(RecipeIntentIn):
    model_config = ConfigDict(from_attributes=True)

    recipe_version_id: str
    updated_at: datetime


class FermentableLineIn(BaseModel):
    ingredient_id: Optional[str] = None
    ingredient_name: str = Field(min_length=1, max_length=200)
    manufacturer: Optional[str] = None
    amount: Decimal
    unit: QuantityUnit
    color_lovibond: Optional[Decimal] = None
    potential_sg: Optional[Decimal] = None
    yield_percent: Optional[Decimal] = None
    sort_order: int = 0

    @field_validator("amount")
    @classmethod
    def positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("amount must be greater than zero")
        return value


class HopLineIn(BaseModel):
    ingredient_id: Optional[str] = None
    ingredient_name: str = Field(min_length=1, max_length=200)
    manufacturer: Optional[str] = None
    amount: Decimal
    unit: QuantityUnit
    alpha_acid: Optional[Decimal] = None
    stage: HopStage
    time_minutes: Optional[int] = None
    sort_order: int = 0

    @field_validator("amount")
    @classmethod
    def positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("amount must be greater than zero")
        return value


class YeastLineIn(BaseModel):
    ingredient_id: Optional[str] = None
    ingredient_name: str = Field(min_length=1, max_length=200)
    manufacturer: Optional[str] = None
    amount: Optional[Decimal] = None
    unit: Optional[QuantityUnit] = None
    expected_attenuation: Optional[Decimal] = None
    temperature_min_c: Optional[Decimal] = None
    temperature_max_c: Optional[Decimal] = None
    sort_order: int = 0


class AdjunctLineIn(BaseModel):
    ingredient_id: Optional[str] = None
    ingredient_name: str = Field(min_length=1, max_length=200)
    amount: Decimal
    unit: QuantityUnit
    notes: Optional[str] = None
    sort_order: int = 0

    @field_validator("amount")
    @classmethod
    def positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("amount must be greater than zero")
        return value


class WaterAdditionLineIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    amount: Decimal
    unit: QuantityUnit
    stage: Optional[str] = None
    sort_order: int = 0

    @field_validator("amount")
    @classmethod
    def positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("amount must be greater than zero")
        return value


class MashStepIn(BaseModel):
    step_name: str = "Infusion"
    target_temperature_c: Decimal
    duration_minutes: int = Field(gt=0)
    mash_water_volume: Optional[Decimal] = None
    mash_water_unit: Optional[VolumeUnit] = None
    sparge_water_volume: Optional[Decimal] = None
    sparge_water_unit: Optional[VolumeUnit] = None
    sort_order: int = 0


class TargetIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    value: Optional[str] = None
    unit: Optional[str] = None
    notes: Optional[str] = None


class RecipeVersionBody(BaseModel):
    batch_size: Decimal
    batch_size_unit: VolumeUnit
    equipment_profile_id: Optional[str] = None
    brewhouse_efficiency: Optional[Decimal] = None
    boil_time_minutes: Optional[int] = None
    mash_method: Optional[MashMethod] = None
    notes: Optional[str] = None
    change_summary: Optional[str] = None
    intent: Optional[RecipeIntentIn] = None
    fermentables: list[FermentableLineIn] = Field(default_factory=list)
    hops: list[HopLineIn] = Field(default_factory=list)
    yeasts: list[YeastLineIn] = Field(default_factory=list)
    adjuncts: list[AdjunctLineIn] = Field(default_factory=list)
    water_additions: list[WaterAdditionLineIn] = Field(default_factory=list)
    mash_steps: list[MashStepIn] = Field(default_factory=list)
    targets: list[TargetIn] = Field(default_factory=list)

    @field_validator("batch_size")
    @classmethod
    def positive_batch(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("batch_size must be greater than zero")
        return value

    @field_validator("brewhouse_efficiency")
    @classmethod
    def efficiency(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is None:
            return value
        if value <= 0 or value > 100:
            raise ValueError("brewhouse_efficiency must be > 0 and <= 100")
        return value


class RecipeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    style: Optional[str] = None
    description: Optional[str] = None
    version: RecipeVersionBody

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned


class RecipeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    style: Optional[str] = None
    description: Optional[str] = None
    status: Optional[RecipeStatus] = None


class NewRecipeVersion(BaseModel):
    """Create a new version from formulation changes (does not mutate parent)."""

    change_summary: Optional[str] = None
    version: RecipeVersionBody


class RecipeClone(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class FermentableLineRead(FermentableLineIn):
    model_config = ConfigDict(from_attributes=True)
    id: str


class HopLineRead(HopLineIn):
    model_config = ConfigDict(from_attributes=True)
    id: str


class YeastLineRead(YeastLineIn):
    model_config = ConfigDict(from_attributes=True)
    id: str


class AdjunctLineRead(AdjunctLineIn):
    model_config = ConfigDict(from_attributes=True)
    id: str


class WaterAdditionLineRead(WaterAdditionLineIn):
    model_config = ConfigDict(from_attributes=True)
    id: str


class MashStepRead(MashStepIn):
    model_config = ConfigDict(from_attributes=True)
    id: str


class TargetRead(TargetIn):
    model_config = ConfigDict(from_attributes=True)
    id: str


class RecipeVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recipe_id: str
    version_number: int
    parent_version_id: Optional[str]
    change_summary: Optional[str]
    status: RecipeVersionStatus
    batch_size: Decimal
    batch_size_unit: VolumeUnit
    equipment_profile_id: Optional[str]
    brewhouse_efficiency: Optional[Decimal]
    boil_time_minutes: Optional[int]
    mash_method: Optional[MashMethod]
    notes: Optional[str]
    created_by: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    intent: Optional[RecipeIntentRead] = None
    fermentables: list[FermentableLineRead] = Field(default_factory=list)
    hops: list[HopLineRead] = Field(default_factory=list)
    yeasts: list[YeastLineRead] = Field(default_factory=list)
    adjuncts: list[AdjunctLineRead] = Field(default_factory=list)
    water_additions: list[WaterAdditionLineRead] = Field(default_factory=list)
    mash_steps: list[MashStepRead] = Field(default_factory=list)
    targets: list[TargetRead] = Field(default_factory=list)


class RecipeVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recipe_id: str
    version_number: int
    status: RecipeVersionStatus
    change_summary: Optional[str]
    created_at: datetime


class RecipeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    brewery_id: str
    name: str
    style: Optional[str]
    description: Optional[str]
    status: RecipeStatus
    current_version_id: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime


class RecipeDetail(RecipeRead):
    current_version: Optional[RecipeVersionRead] = None
    versions: list[RecipeVersionSummary] = Field(default_factory=list)
