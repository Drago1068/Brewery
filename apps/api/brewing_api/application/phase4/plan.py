from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from brewing_api.domain.fermentation.constants import PLAN_SCHEMA_VERSION, STAGE_TYPES
from brewing_api.domain.recipes.models import RecipeVersion

MATERIALIZATION_RULE_VERSION = "phase4-materialization-v1"
PLAN_KIND_DEFAULT = "FERMENTATION_DEFAULT"


@dataclass(frozen=True)
class FermentationPlanStep:
    plan_step_id: uuid.UUID
    canonical_stage_type: str
    occurrence_number: int
    name: str
    required: bool = True


@dataclass(frozen=True)
class FermentationLogicalPlan:
    plan_kind: str
    steps: tuple[FermentationPlanStep, ...]
    additions: tuple[dict[str, Any], ...]


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def logical_plan_hash(plan: FermentationLogicalPlan) -> str:
    body = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "materialization_rule_version": MATERIALIZATION_RULE_VERSION,
        "plan_kind": plan.plan_kind,
        "steps": [
            {
                "plan_step_id": str(step.plan_step_id),
                "canonical_stage_type": step.canonical_stage_type,
                "occurrence_number": step.occurrence_number,
                "name": step.name,
                "required": step.required,
            }
            for step in plan.steps
        ],
        "additions": plan.additions,
    }
    return hashlib.sha256(_canonical_json(body).encode()).hexdigest()


def plan_preview_hash(plan: FermentationLogicalPlan) -> str:
    preview = {
        "plan_kind": plan.plan_kind,
        "stage_types": [step.canonical_stage_type for step in plan.steps],
        "addition_count": len(plan.additions),
    }
    return hashlib.sha256(_canonical_json(preview).encode()).hexdigest()


def materialize_default_plan(
    *,
    recipe_version_id: uuid.UUID,
    fermentation_additions: list[dict[str, Any]] | None = None,
) -> FermentationLogicalPlan:
    del recipe_version_id
    steps = [
        FermentationPlanStep(
            plan_step_id=uuid.uuid5(uuid.NAMESPACE_OID, "phase4:pitch-confirmed"),
            canonical_stage_type="PITCH_CONFIRMED",
            occurrence_number=1,
            name="Pitch confirmed",
            required=True,
        ),
        FermentationPlanStep(
            plan_step_id=uuid.uuid5(uuid.NAMESPACE_OID, "phase4:active-fermentation"),
            canonical_stage_type="ACTIVE_FERMENTATION",
            occurrence_number=1,
            name="Active fermentation",
            required=True,
        ),
        FermentationPlanStep(
            plan_step_id=uuid.uuid5(uuid.NAMESPACE_OID, "phase4:conditioning"),
            canonical_stage_type="CONDITIONING",
            occurrence_number=1,
            name="Conditioning",
            required=False,
        ),
        FermentationPlanStep(
            plan_step_id=uuid.uuid5(uuid.NAMESPACE_OID, "phase4:handoff-ready"),
            canonical_stage_type="HANDOFF_READY",
            occurrence_number=1,
            name="Packaging handoff ready",
            required=True,
        ),
    ]
    for step in steps:
        if step.canonical_stage_type not in STAGE_TYPES:
            raise ValueError(f"Unsupported stage type {step.canonical_stage_type}")
    return FermentationLogicalPlan(
        plan_kind=PLAN_KIND_DEFAULT,
        steps=tuple(steps),
        additions=tuple(fermentation_additions or []),
    )


def recipe_snapshot_payload(version: RecipeVersion) -> dict[str, Any]:
    pitch_rate: str | None = None
    if version.calculation_inputs and isinstance(version.calculation_inputs, dict):
        raw_rate = version.calculation_inputs.get("pitch_rate_million_per_ml_plato")
        if raw_rate is not None:
            pitch_rate = str(raw_rate)
    return {
        "recipe_version_id": str(version.id),
        "batch_size_liters": None
        if version.batch_size_liters is None
        else str(version.batch_size_liters),
        "target_og": None if version.target_og is None else str(version.target_og),
        "target_fg": None if version.target_fg is None else str(version.target_fg),
        "apparent_attenuation": None
        if version.apparent_attenuation is None
        else str(version.apparent_attenuation),
        "pitch_rate_million_per_ml_plato": pitch_rate,
    }


def plan_snapshot_payload(
    plan: FermentationLogicalPlan,
    *,
    recipe_snapshot: dict[str, Any] | None = None,
    conditioning_required: bool = False,
    conditioning_mode: str | None = None,
    conditioning_duration_minutes: int | None = None,
    conditioning_temperature_c: str | None = None,
    temperature_tolerance_c: str = "1.0",
) -> dict[str, Any]:
    payload = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "materialization_rule_version": MATERIALIZATION_RULE_VERSION,
        "plan_kind": plan.plan_kind,
        "conditioning_required": conditioning_required,
        "conditioning_mode": conditioning_mode,
        "conditioning_duration_minutes": conditioning_duration_minutes,
        "conditioning_temperature_c": conditioning_temperature_c,
        "temperature_tolerance_c": temperature_tolerance_c,
        "steps": [
            {
                "plan_step_id": str(step.plan_step_id),
                "canonical_stage_type": step.canonical_stage_type,
                "occurrence_number": step.occurrence_number,
                "name": step.name,
                "required": step.required,
            }
            for step in plan.steps
        ],
        "additions": list(plan.additions),
    }
    if recipe_snapshot is not None:
        payload["recipe_snapshot"] = recipe_snapshot
    return payload


def plan_conditioning_required(snapshot_payload: dict[str, Any] | None) -> bool:
    if not snapshot_payload:
        return False
    if "conditioning_required" in snapshot_payload:
        return bool(snapshot_payload["conditioning_required"])
    if snapshot_payload.get("conditioning_mode") is not None:
        return True
    if snapshot_payload.get("conditioning_duration_minutes") is not None:
        return True
    if snapshot_payload.get("conditioning_temperature_c") is not None:
        return True
    return False
