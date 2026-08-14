import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str


class RecipeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    target_mash_temperature: Decimal = Field(ge=100, le=180, decimal_places=2)
    target_mash_ph: Decimal = Field(ge=0, le=14, decimal_places=2)
    mash_ph_tolerance: Decimal = Field(ge=0, le=2, decimal_places=2)
    target_mash_gravity: Decimal = Field(ge=Decimal("1.000"), le=Decimal("1.200"), decimal_places=3)
    mash_gravity_tolerance: Decimal = Field(ge=0, le=Decimal("0.100"), decimal_places=3)
    planned_mash_duration_minutes: int = Field(ge=1, le=240)


class RecipeResponse(BaseModel):
    id: uuid.UUID
    name: str
    version_id: uuid.UUID
    version_number: int
    target_mash_temperature: Decimal
    mash_temperature_unit: str
    target_mash_ph: Decimal
    mash_ph_tolerance: Decimal
    target_mash_gravity: Decimal
    mash_gravity_tolerance: Decimal
    planned_mash_duration_minutes: int


class BrewSessionCreate(BaseModel):
    recipe_version_id: uuid.UUID
    operation_id: str = Field(min_length=1, max_length=64)
    plan_preview_hash: str | None = None
    addition_repeat_declarations: list[dict] | None = None


class MeasurementCreate(BaseModel):
    measurement_type: str
    value: Decimal
    unit: str
    measured_at: datetime | None = None
    note: str | None = Field(default=None, max_length=2000)
    instrument: str | None = Field(default=None, max_length=160)
    entry_method: Literal["MANUAL", "VOICE_CONFIRMED"] = "MANUAL"
    operation_id: str = Field(min_length=1, max_length=64)
    late_entry_reason: str | None = Field(default=None, max_length=1000)
    method: str | None = Field(default=None, max_length=32)
    sample_temperature_c: Decimal | None = None
    temperature_compensated: bool | None = None
    vessel: str | None = Field(default=None, max_length=40)
    raw_value: Decimal | None = None
    raw_unit: str | None = Field(default=None, max_length=16)
    conversion_model_id: str | None = Field(default=None, max_length=80)

    def model_post_init(self, __context: object) -> None:
        if self.measurement_type == "MASH_PH" and not Decimal("0") <= self.value <= Decimal("14"):
            raise ValueError("Mash pH must be between 0 and 14")
        gravity_types = {
            "MASH_GRAVITY",
            "POST_MASH_GRAVITY",
            "PRE_BOIL_GRAVITY",
            "ORIGINAL_GRAVITY",
        }
        if self.measurement_type == "MASH_GRAVITY":
            gravity_is_valid = Decimal("1.000") <= self.value <= Decimal("1.200")
            if not gravity_is_valid:
                raise ValueError("Mash gravity must be between 1.000 and 1.200 SG")
        elif self.measurement_type in gravity_types:
            gravity_is_valid = Decimal("0.900") <= self.value <= Decimal("1.300")
            if not gravity_is_valid:
                raise ValueError("Gravity must be between 0.900 and 1.300 SG")
        if self.measurement_type in {
            "MASH_IN_TEMPERATURE",
            "MASH_REST_TEMPERATURE",
            "KNOCKOUT_TEMPERATURE",
            "PITCH_TEMPERATURE",
        } and not Decimal("-10") <= self.value <= Decimal("120"):
            raise ValueError("Temperature must be between -10 and 120 degC")
        if self.measurement_type in {"PRE_BOIL_VOLUME", "KNOCKOUT_VOLUME"} and self.value <= 0:
            raise ValueError("Volume must be greater than 0 L")


class IdStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
