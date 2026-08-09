"""Pydantic schemas for brewery and equipment APIs."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import (
    MASH_RELEVANT_TYPES,
    EquipmentSystemType,
    PreferredUnits,
    VolumeUnit,
)


def _positive(value: Decimal, field_name: str) -> Decimal:
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return value


def _efficiency(value: Decimal) -> Decimal:
    if value <= 0 or value > 100:
        raise ValueError("efficiency must be greater than 0 and at most 100 (percent)")
    return value


class BreweryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    preferred_units: PreferredUnits
    timezone: str = Field(min_length=1, max_length=64)
    default_batch_size: Decimal
    default_batch_size_unit: VolumeUnit
    default_brewhouse_efficiency: Decimal

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("default_batch_size")
    @classmethod
    def validate_batch(cls, value: Decimal) -> Decimal:
        return _positive(value, "default_batch_size")

    @field_validator("default_brewhouse_efficiency")
    @classmethod
    def validate_efficiency(cls, value: Decimal) -> Decimal:
        return _efficiency(value)

    @model_validator(mode="after")
    def units_alignment(self) -> "BreweryCreate":
        if self.preferred_units == PreferredUnits.US and self.default_batch_size_unit != VolumeUnit.GAL:
            raise ValueError("US preferred units require default_batch_size_unit=gal")
        if self.preferred_units == PreferredUnits.METRIC and self.default_batch_size_unit != VolumeUnit.L:
            raise ValueError("METRIC preferred units require default_batch_size_unit=L")
        return self


class BreweryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    preferred_units: Optional[PreferredUnits] = None
    timezone: Optional[str] = Field(default=None, min_length=1, max_length=64)
    default_batch_size: Optional[Decimal] = None
    default_batch_size_unit: Optional[VolumeUnit] = None
    default_brewhouse_efficiency: Optional[Decimal] = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("default_batch_size")
    @classmethod
    def validate_batch(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is None:
            return value
        return _positive(value, "default_batch_size")

    @field_validator("default_brewhouse_efficiency")
    @classmethod
    def validate_efficiency(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is None:
            return value
        return _efficiency(value)


class BreweryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    preferred_units: PreferredUnits
    timezone: str
    default_batch_size: Decimal
    default_batch_size_unit: VolumeUnit
    default_brewhouse_efficiency: Decimal
    created_by: str
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime


class EquipmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    system_type: EquipmentSystemType
    target_batch_size: Decimal
    target_batch_size_unit: VolumeUnit
    kettle_capacity: Decimal
    kettle_capacity_unit: VolumeUnit
    mash_capacity: Optional[Decimal] = None
    mash_capacity_unit: Optional[VolumeUnit] = None
    boil_off_rate: Optional[Decimal] = None
    boil_off_rate_unit: Optional[str] = Field(default=None, max_length=16)
    trub_loss: Optional[Decimal] = None
    trub_loss_unit: Optional[VolumeUnit] = None
    fermenter_loss: Optional[Decimal] = None
    fermenter_loss_unit: Optional[VolumeUnit] = None
    typical_brewhouse_efficiency: Optional[Decimal] = None
    notes: Optional[str] = None
    active: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("target_batch_size", "kettle_capacity")
    @classmethod
    def validate_positive_required(cls, value: Decimal, info) -> Decimal:
        return _positive(value, info.field_name)

    @field_validator("mash_capacity", "boil_off_rate", "trub_loss", "fermenter_loss")
    @classmethod
    def validate_positive_optional(cls, value: Optional[Decimal], info) -> Optional[Decimal]:
        if value is None:
            return value
        return _positive(value, info.field_name)

    @field_validator("typical_brewhouse_efficiency")
    @classmethod
    def validate_efficiency(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is None:
            return value
        return _efficiency(value)

    @model_validator(mode="after")
    def mash_rules(self) -> "EquipmentCreate":
        mash_relevant = self.system_type in MASH_RELEVANT_TYPES
        if self.system_type == EquipmentSystemType.EXTRACT:
            # Extract brewers should not be forced to supply mash capacity.
            return self
        if mash_relevant and self.mash_capacity is not None and self.mash_capacity_unit is None:
            raise ValueError("mash_capacity_unit is required when mash_capacity is set")
        if self.mash_capacity is None and self.mash_capacity_unit is not None:
            raise ValueError("mash_capacity is required when mash_capacity_unit is set")
        if self.boil_off_rate is not None and not self.boil_off_rate_unit:
            raise ValueError("boil_off_rate_unit is required when boil_off_rate is set")
        if self.trub_loss is not None and self.trub_loss_unit is None:
            raise ValueError("trub_loss_unit is required when trub_loss is set")
        if self.fermenter_loss is not None and self.fermenter_loss_unit is None:
            raise ValueError("fermenter_loss_unit is required when fermenter_loss is set")
        if self.kettle_capacity < self.target_batch_size:
            # Warning-worthy for readiness later; for create we allow but flag via API? 
            # Keep as soft validation — capacity smaller than batch is suspicious.
            # Epic readiness will block; store allowed with note that validation is explicit.
            pass
        return self


class EquipmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    system_type: Optional[EquipmentSystemType] = None
    target_batch_size: Optional[Decimal] = None
    target_batch_size_unit: Optional[VolumeUnit] = None
    kettle_capacity: Optional[Decimal] = None
    kettle_capacity_unit: Optional[VolumeUnit] = None
    mash_capacity: Optional[Decimal] = None
    mash_capacity_unit: Optional[VolumeUnit] = None
    boil_off_rate: Optional[Decimal] = None
    boil_off_rate_unit: Optional[str] = Field(default=None, max_length=16)
    trub_loss: Optional[Decimal] = None
    trub_loss_unit: Optional[VolumeUnit] = None
    fermenter_loss: Optional[Decimal] = None
    fermenter_loss_unit: Optional[VolumeUnit] = None
    typical_brewhouse_efficiency: Optional[Decimal] = None
    notes: Optional[str] = None
    active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator(
        "target_batch_size",
        "kettle_capacity",
        "mash_capacity",
        "boil_off_rate",
        "trub_loss",
        "fermenter_loss",
    )
    @classmethod
    def validate_positive_optional(cls, value: Optional[Decimal], info) -> Optional[Decimal]:
        if value is None:
            return value
        return _positive(value, info.field_name)

    @field_validator("typical_brewhouse_efficiency")
    @classmethod
    def validate_efficiency(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is None:
            return value
        return _efficiency(value)


class EquipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    brewery_id: str
    name: str
    system_type: EquipmentSystemType
    target_batch_size: Decimal
    target_batch_size_unit: VolumeUnit
    kettle_capacity: Decimal
    kettle_capacity_unit: VolumeUnit
    mash_capacity: Optional[Decimal]
    mash_capacity_unit: Optional[VolumeUnit]
    boil_off_rate: Optional[Decimal]
    boil_off_rate_unit: Optional[str]
    trub_loss: Optional[Decimal]
    trub_loss_unit: Optional[VolumeUnit]
    fermenter_loss: Optional[Decimal]
    fermenter_loss_unit: Optional[VolumeUnit]
    typical_brewhouse_efficiency: Optional[Decimal]
    notes: Optional[str]
    active: bool
    created_by: str
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime
