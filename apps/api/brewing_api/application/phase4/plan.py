from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from brewing_api.domain.fermentation.constants import PLAN_SCHEMA_VERSION, STAGE_TYPES

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


def plan_snapshot_payload(plan: FermentationLogicalPlan) -> dict[str, Any]:
    return {
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
        "additions": list(plan.additions),
    }
