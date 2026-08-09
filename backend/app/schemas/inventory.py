"""Ingredient and inventory API schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import (
    FermentableType,
    HopType,
    IngredientCategory,
    InventoryTransactionType,
    QuantityUnit,
    YeastType,
)


class FermentableProfileIn(BaseModel):
    fermentable_type: FermentableType
    color_lovibond: Optional[Decimal] = None
    potential_sg: Optional[Decimal] = None
    yield_percent: Optional[Decimal] = None


class HopProfileIn(BaseModel):
    hop_type: HopType
    default_alpha_acid: Optional[Decimal] = None
    beta_acid: Optional[Decimal] = None
    aroma_descriptors: Optional[str] = None


class YeastProfileIn(BaseModel):
    yeast_type: YeastType
    strain: Optional[str] = None
    attenuation_min: Optional[Decimal] = None
    attenuation_max: Optional[Decimal] = None
    temperature_min_c: Optional[Decimal] = None
    temperature_max_c: Optional[Decimal] = None

    @model_validator(mode="after")
    def attenuation_order(self) -> "YeastProfileIn":
        if (
            self.attenuation_min is not None
            and self.attenuation_max is not None
            and self.attenuation_min > self.attenuation_max
        ):
            raise ValueError("attenuation_min cannot exceed attenuation_max")
        if (
            self.temperature_min_c is not None
            and self.temperature_max_c is not None
            and self.temperature_min_c > self.temperature_max_c
        ):
            raise ValueError("temperature_min_c cannot exceed temperature_max_c")
        return self


class IngredientCreate(BaseModel):
    category: IngredientCategory
    name: str = Field(min_length=1, max_length=200)
    manufacturer: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    default_unit: QuantityUnit
    active: bool = True
    fermentable_profile: Optional[FermentableProfileIn] = None
    hop_profile: Optional[HopProfileIn] = None
    yeast_profile: Optional[YeastProfileIn] = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @model_validator(mode="after")
    def profile_matches_category(self) -> "IngredientCreate":
        if self.category == IngredientCategory.FERMENTABLE and self.fermentable_profile is None:
            raise ValueError("fermentable_profile is required for FERMENTABLE ingredients")
        if self.category == IngredientCategory.HOP and self.hop_profile is None:
            raise ValueError("hop_profile is required for HOP ingredients")
        if self.category == IngredientCategory.YEAST and self.yeast_profile is None:
            raise ValueError("yeast_profile is required for YEAST ingredients")
        if self.category != IngredientCategory.FERMENTABLE and self.fermentable_profile is not None:
            raise ValueError("fermentable_profile only valid for FERMENTABLE")
        if self.category != IngredientCategory.HOP and self.hop_profile is not None:
            raise ValueError("hop_profile only valid for HOP")
        if self.category != IngredientCategory.YEAST and self.yeast_profile is not None:
            raise ValueError("yeast_profile only valid for YEAST")
        return self


class IngredientUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    manufacturer: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    default_unit: Optional[QuantityUnit] = None
    active: Optional[bool] = None
    fermentable_profile: Optional[FermentableProfileIn] = None
    hop_profile: Optional[HopProfileIn] = None
    yeast_profile: Optional[YeastProfileIn] = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned


class FermentableProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fermentable_type: FermentableType
    color_lovibond: Optional[Decimal]
    potential_sg: Optional[Decimal]
    yield_percent: Optional[Decimal]


class HopProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hop_type: HopType
    default_alpha_acid: Optional[Decimal]
    beta_acid: Optional[Decimal]
    aroma_descriptors: Optional[str]


class YeastProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    yeast_type: YeastType
    strain: Optional[str]
    attenuation_min: Optional[Decimal]
    attenuation_max: Optional[Decimal]
    temperature_min_c: Optional[Decimal]
    temperature_max_c: Optional[Decimal]


class IngredientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    brewery_id: str
    category: IngredientCategory
    name: str
    manufacturer: Optional[str]
    description: Optional[str]
    default_unit: QuantityUnit
    active: bool
    created_by: str
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    fermentable_profile: Optional[FermentableProfileRead] = None
    hop_profile: Optional[HopProfileRead] = None
    yeast_profile: Optional[YeastProfileRead] = None


class InventoryReceive(BaseModel):
    ingredient_id: str
    quantity: Decimal
    unit: QuantityUnit
    supplier: Optional[str] = None
    supplier_lot_number: Optional[str] = None
    manufacturer_lot_number: Optional[str] = None
    received_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    purchase_cost: Optional[Decimal] = None
    storage_location: Optional[str] = None
    opened_at: Optional[datetime] = None
    notes: Optional[str] = None
    actual_alpha_acid: Optional[Decimal] = None
    reason: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("quantity must be greater than zero")
        return value


class InventoryAdjust(BaseModel):
    lot_id: str
    quantity: Decimal  # signed: + increase, - decrease
    reason: str = Field(min_length=1)

    @field_validator("quantity")
    @classmethod
    def non_zero(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("quantity must be non-zero")
        return value


class InventoryConsume(BaseModel):
    lot_id: str
    quantity: Decimal
    reason: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("quantity must be greater than zero")
        return value


class InventoryWaste(BaseModel):
    lot_id: str
    quantity: Decimal
    reason: str = Field(min_length=1)

    @field_validator("quantity")
    @classmethod
    def positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("quantity must be greater than zero")
        return value


class InventoryReserve(BaseModel):
    lot_id: str
    quantity: Decimal
    reason: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("quantity must be greater than zero")
        return value


class LotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    brewery_id: str
    ingredient_id: str
    supplier: Optional[str]
    supplier_lot_number: Optional[str]
    manufacturer_lot_number: Optional[str]
    received_date: Optional[datetime]
    expiration_date: Optional[datetime]
    quantity_received: Decimal
    unit: QuantityUnit
    purchase_cost: Optional[Decimal]
    storage_location: Optional[str]
    opened_at: Optional[datetime]
    notes: Optional[str]
    actual_alpha_acid: Optional[Decimal]
    quantity_on_hand: Decimal
    quantity_reserved: Decimal
    created_by: str
    created_at: datetime
    updated_at: datetime


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    brewery_id: str
    ingredient_lot_id: str
    transaction_type: InventoryTransactionType
    quantity: Decimal
    unit: QuantityUnit
    occurred_at: datetime
    reason: Optional[str]
    reference_type: Optional[str]
    reference_id: Optional[str]
    created_by: str
    created_at: datetime


class InventoryAvailabilityRow(BaseModel):
    ingredient_id: str
    name: str
    category: IngredientCategory
    manufacturer: Optional[str]
    unit: QuantityUnit
    quantity_on_hand: Decimal
    quantity_reserved: Decimal
    quantity_available: Decimal
    storage_locations: list[str]
    freshness: str  # OK | OPENED | EXPIRING | EXPIRED | UNKNOWN
    lot_count: int
