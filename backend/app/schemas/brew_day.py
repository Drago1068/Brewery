"""Brew day (E2A-1/E2A-2) API schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import BrewTransitionCommand


class ReadinessAcknowledgement(BaseModel):
    acknowledged: bool = True
    note: Optional[str] = None
    actor_id: Optional[str] = None


class BrewPlanCreate(BaseModel):
    client_submission_id: str = Field(min_length=1, max_length=128)
    readiness_acknowledgement: Optional[ReadinessAcknowledgement] = None


class BrewPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    brewery_id: str
    recipe_id: str
    recipe_version_id: str
    status: str
    batch_size: Decimal
    batch_size_unit: str
    brewhouse_efficiency: Optional[Decimal] = None
    equipment_profile_id: Optional[str] = None
    equipment_snapshot: Optional[dict[str, Any]] = None
    recipe_snapshot: dict[str, Any]
    planned_calculation_snapshot: dict[str, Any]
    readiness_status: str
    readiness_summary: str
    readiness_checks_snapshot: list[Any]
    readiness_acknowledged: bool
    readiness_acknowledged_at: Optional[datetime] = None
    readiness_acknowledged_by: Optional[str] = None
    readiness_acknowledgement_note: Optional[str] = None
    created_by: str
    created_at: datetime


class BrewSessionCreate(BaseModel):
    client_submission_id: str = Field(min_length=1, max_length=128)
    client_context: Optional[str] = None


class StageOccurrenceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    stage_code: str
    sequence_no: int
    status: str
    entered_at: Optional[datetime] = None
    exited_at: Optional[datetime] = None
    skip_reason: Optional[str] = None


class BrewSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    brew_plan_id: str
    brewery_id: str
    status: str
    current_stage_code: Optional[str] = None
    version: int
    started_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    abort_reason: Optional[str] = None
    created_by: str
    created_at: datetime
    stage_occurrences: list[StageOccurrenceSummary]


class SessionTransitionRequest(BaseModel):
    client_submission_id: str = Field(min_length=1, max_length=128)
    expected_session_version: int = Field(ge=1)
    command: BrewTransitionCommand
    skip_reason: Optional[str] = None
    abort_reason: Optional[str] = None
    client_occurred_at: Optional[datetime] = None


class BrewEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    brewery_id: str
    brew_plan_id: Optional[str] = None
    brew_session_id: Optional[str] = None
    event_type: str
    actor_id: str
    occurred_at: datetime
    client_occurred_at: Optional[datetime] = None
    payload: dict[str, Any]
    client_submission_id: Optional[str] = None
    correlation_key: Optional[str] = None
