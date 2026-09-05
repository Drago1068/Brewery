from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ValidationConflictError
from brewing_api.domain.fermentation.constants import CONDITIONING_MODES, PLAN_SCHEMA_VERSION, STAGE_TYPES
from brewing_api.domain.recipes.models import RecipeIngredient, RecipeProcessStep, RecipeVersion

MATERIALIZATION_RULE_VERSION = "phase4-materialization-v1"
PLAN_KIND_DEFAULT = "FERMENTATION_DEFAULT"
REQUIREMENT_TEMPLATE_NAMESPACE = uuid.UUID("c4e21b8a-7d0e-5f33-9a14-8b6c2d91e0aa")
DEFAULT_TOLERANCE_C = Decimal("1.0")
DEFAULT_TOLERANCE_PROVENANCE = "PHASE4_DEFAULT_TOLERANCE_V1"
ADDITION_USE_STAGES = frozenset({"FERMENTATION", "DRY_HOP"})


class PlanMaterializationError(ValidationConflictError):
    def __init__(self, message: str, failures: list[dict[str, Any]]):
        super().__init__(
            message,
            code="PLAN_MATERIALIZATION_FAILED",
            extra={"failures": failures},
        )
        self.failures = failures


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
    requirement_templates: tuple[dict[str, Any], ...] = ()
    fermentation_temperature_c: str | None = None
    fermentation_temperature_status: str = "UNSPECIFIED"
    fermentation_duration_minutes: int | None = None
    conditioning_required: bool = False
    conditioning_mode: str | None = None
    conditioning_duration_minutes: int | None = None
    conditioning_temperature_c: str | None = None
    temperature_tolerance_c: str = "1.0"
    temperature_tolerance_provenance: str = DEFAULT_TOLERANCE_PROVENANCE
    schedule: tuple[dict[str, Any], ...] | None = None
    conditioning_schedule: tuple[dict[str, Any], ...] | None = None
    required_ph: bool = False


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def phase4_requirement_template_id(
    recipe_version_id: uuid.UUID,
    requirement_class: str,
    stable_source: str,
) -> uuid.UUID:
    return uuid.uuid5(
        REQUIREMENT_TEMPLATE_NAMESPACE,
        f"phase4-plan-v1:{recipe_version_id}:{requirement_class}:{stable_source}",
    )


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
        "additions": list(plan.additions),
        "requirement_templates": list(plan.requirement_templates),
        "fermentation_temperature_c": plan.fermentation_temperature_c,
        "fermentation_temperature_status": plan.fermentation_temperature_status,
        "fermentation_duration_minutes": plan.fermentation_duration_minutes,
        "conditioning_required": plan.conditioning_required,
        "conditioning_mode": plan.conditioning_mode,
        "conditioning_duration_minutes": plan.conditioning_duration_minutes,
        "conditioning_temperature_c": plan.conditioning_temperature_c,
        "temperature_tolerance_c": plan.temperature_tolerance_c,
        "temperature_tolerance_provenance": plan.temperature_tolerance_provenance,
        "schedule": None if plan.schedule is None else list(plan.schedule),
        "conditioning_schedule": None
        if plan.conditioning_schedule is None
        else list(plan.conditioning_schedule),
        "required_ph": plan.required_ph,
    }
    return hashlib.sha256(_canonical_json(body).encode()).hexdigest()


def plan_preview_hash(plan: FermentationLogicalPlan) -> str:
    preview = {
        "plan_kind": plan.plan_kind,
        "stage_types": [step.canonical_stage_type for step in plan.steps],
        "addition_count": len(plan.additions),
        "has_schedule": plan.schedule is not None,
        "conditioning_required": plan.conditioning_required,
    }
    return hashlib.sha256(_canonical_json(preview).encode()).hexdigest()


def _default_steps() -> tuple[FermentationPlanStep, ...]:
    steps = (
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
    )
    for step in steps:
        if step.canonical_stage_type not in STAGE_TYPES:
            raise ValueError(f"Unsupported stage type {step.canonical_stage_type}")
    return steps


def _parse_decimal(raw: Any, *, field: str) -> Decimal:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PlanMaterializationError(
            "Plan materialization failed",
            [{"reason": "INVALID_DECIMAL", "field": field}],
        ) from exc


def _normalize_schedule(raw: Any, *, field: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw, list):
        raise PlanMaterializationError(
            "Plan materialization failed",
            [{"reason": "INVALID_SCHEDULE_SHAPE", "field": field}],
        )
    parsed: list[dict[str, Any]] = []
    seen_offsets: set[int] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise PlanMaterializationError(
                "Plan materialization failed",
                [{"reason": "INVALID_SCHEDULE_ELEMENT", "field": field, "index": index}],
            )
        if "effective_offset_minutes" not in item or "target_temp_c" not in item:
            raise PlanMaterializationError(
                "Plan materialization failed",
                [{"reason": "INVALID_SCHEDULE_ELEMENT", "field": field, "index": index}],
            )
        try:
            offset = int(item["effective_offset_minutes"])
        except (TypeError, ValueError) as exc:
            raise PlanMaterializationError(
                "Plan materialization failed",
                [{"reason": "INVALID_SCHEDULE_OFFSET", "field": field, "index": index}],
            ) from exc
        if offset < 0:
            raise PlanMaterializationError(
                "Plan materialization failed",
                [{"reason": "NEGATIVE_SCHEDULE_OFFSET", "field": field, "index": index}],
            )
        if offset in seen_offsets:
            raise PlanMaterializationError(
                "Plan materialization failed",
                [{"reason": "DUPLICATE_SCHEDULE_OFFSET", "field": field, "offset": offset}],
            )
        seen_offsets.add(offset)
        temp = _parse_decimal(item["target_temp_c"], field=f"{field}[{index}].target_temp_c")
        parsed.append(
            {
                "effective_offset_minutes": offset,
                "target_temp_c": str(temp),
            }
        )
    parsed.sort(key=lambda row: row["effective_offset_minutes"])
    return tuple(parsed)


def _ordered_fermentation_additions(
    db: Session, recipe_version_id: uuid.UUID
) -> list[RecipeIngredient]:
    rows = list(
        db.scalars(
            select(RecipeIngredient).where(
                RecipeIngredient.recipe_version_id == recipe_version_id,
                RecipeIngredient.use_stage.in_(tuple(ADDITION_USE_STAGES)),
            )
        ).all()
    )
    # §10.1: use_stage ASC, timing_minutes ASC NULLS FIRST, ingredient_id ASC, id ASC
    rows.sort(
        key=lambda row: (
            row.use_stage,
            0 if row.timing_minutes is None else 1,
            row.timing_minutes if row.timing_minutes is not None else 0,
            str(row.ingredient_id),
            str(row.id),
        )
    )
    return rows


def _build_requirement_templates(
    recipe_version_id: uuid.UUID,
    *,
    fermentation_temperature_status: str,
    required_ph: bool,
    conditioning_required: bool,
    conditioning_temperature_c: str | None,
    conditioning_duration_minutes: int | None,
    apparent_attenuation: Decimal | None,
    additions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []

    def add(requirement_class: str, stable_source: str, *, required: bool, waivable: bool) -> None:
        template_id = phase4_requirement_template_id(
            recipe_version_id, requirement_class, stable_source
        )
        templates.append(
            {
                "requirement_template_id": str(template_id),
                "requirement_class": requirement_class,
                "stable_source": stable_source,
                "required": required,
                "waivable": waivable,
            }
        )

    add("FERMENTATION_GRAVITY_STABILITY", "default", required=True, waivable=False)
    add(
        "FERMENTATION_TEMPERATURE",
        "default",
        required=fermentation_temperature_status != "UNSPECIFIED",
        waivable=True,
    )
    add("FERMENTATION_PH", "default", required=required_ph, waivable=True)
    if conditioning_required and conditioning_temperature_c is not None:
        add("CONDITIONING_TEMPERATURE", "default", required=True, waivable=True)
    if conditioning_required and conditioning_duration_minutes is not None:
        add("CONDITIONING_DURATION", "default", required=True, waivable=True)
    for addition in additions:
        add(
            "PLANNED_ADDITION",
            addition["stable_source"],
            required=True,
            waivable=True,
        )
    if apparent_attenuation is not None:
        add("ATTENUATION_TARGET", "default", required=True, waivable=True)
    add("ORIGINAL_GRAVITY_KNOWN", "default", required=True, waivable=True)
    return templates


def materialize_default_plan(
    *,
    recipe_version_id: uuid.UUID,
    fermentation_additions: list[dict[str, Any]] | None = None,
) -> FermentationLogicalPlan:
    """Sparse-valid default plan (zero FERMENTATION_FOUNDATION steps)."""
    del recipe_version_id
    return FermentationLogicalPlan(
        plan_kind=PLAN_KIND_DEFAULT,
        steps=_default_steps(),
        additions=tuple(fermentation_additions or []),
        conditioning_required=False,
        fermentation_temperature_status="UNSPECIFIED",
        temperature_tolerance_c=str(DEFAULT_TOLERANCE_C),
        temperature_tolerance_provenance=DEFAULT_TOLERANCE_PROVENANCE,
    )


def materialize_phase4_plan(db: Session, recipe_version: RecipeVersion) -> FermentationLogicalPlan:
    """Materialize phase4-plan-v1 from RecipeVersion sources (§10)."""
    foundation_steps = list(
        db.scalars(
            select(RecipeProcessStep)
            .where(
                RecipeProcessStep.recipe_version_id == recipe_version.id,
                RecipeProcessStep.step_type == "FERMENTATION_FOUNDATION",
            )
            .order_by(RecipeProcessStep.sequence.asc(), RecipeProcessStep.id.asc())
        ).all()
    )
    if len(foundation_steps) > 1:
        raise PlanMaterializationError(
            "Plan materialization failed",
            [{"reason": "DUPLICATE_FERMENTATION_FOUNDATION"}],
        )

    fermentation_temperature_c: str | None = None
    fermentation_temperature_status = "UNSPECIFIED"
    fermentation_duration_minutes: int | None = None
    conditioning_required = False
    conditioning_mode: str | None = None
    conditioning_duration_minutes: int | None = None
    conditioning_temperature_c: str | None = None
    temperature_tolerance_c = DEFAULT_TOLERANCE_C
    temperature_tolerance_provenance = DEFAULT_TOLERANCE_PROVENANCE
    schedule: tuple[dict[str, Any], ...] | None = None
    conditioning_schedule: tuple[dict[str, Any], ...] | None = None
    required_ph = False

    if len(foundation_steps) == 1:
        step = foundation_steps[0]
        if step.temperature_c is not None:
            fermentation_temperature_c = str(step.temperature_c)
            fermentation_temperature_status = "SPECIFIED"
        if step.duration_minutes is not None:
            fermentation_duration_minutes = int(step.duration_minutes)
        details = step.details if isinstance(step.details, dict) else {}
        # Unknown keys ignored (not fatal).
        if "conditioning_mode" in details and details["conditioning_mode"] is not None:
            mode = str(details["conditioning_mode"])
            if mode not in CONDITIONING_MODES:
                raise PlanMaterializationError(
                    "Plan materialization failed",
                    [{"reason": "INVALID_CONDITIONING_MODE", "value": mode}],
                )
            conditioning_mode = mode
        if "conditioning_temperature_c" in details and details["conditioning_temperature_c"] is not None:
            conditioning_temperature_c = str(
                _parse_decimal(
                    details["conditioning_temperature_c"],
                    field="conditioning_temperature_c",
                )
            )
        if "conditioning_duration_minutes" in details and details["conditioning_duration_minutes"] is not None:
            try:
                conditioning_duration_minutes = int(details["conditioning_duration_minutes"])
            except (TypeError, ValueError) as exc:
                raise PlanMaterializationError(
                    "Plan materialization failed",
                    [{"reason": "INVALID_CONDITIONING_DURATION"}],
                ) from exc
            if conditioning_duration_minutes < 0:
                raise PlanMaterializationError(
                    "Plan materialization failed",
                    [{"reason": "NEGATIVE_CONDITIONING_DURATION"}],
                )
        if "temperature_tolerance_c" in details and details["temperature_tolerance_c"] is not None:
            temperature_tolerance_c = _parse_decimal(
                details["temperature_tolerance_c"], field="temperature_tolerance_c"
            )
            if temperature_tolerance_c < 0:
                raise PlanMaterializationError(
                    "Plan materialization failed",
                    [{"reason": "NEGATIVE_TEMPERATURE_TOLERANCE"}],
                )
            temperature_tolerance_provenance = "RECIPE_DETAILS"
        if "required_ph" in details:
            required_ph = bool(details["required_ph"])
        if "schedule" in details:
            schedule = _normalize_schedule(details["schedule"], field="schedule")
        if "conditioning_schedule" in details:
            conditioning_schedule = _normalize_schedule(
                details["conditioning_schedule"], field="conditioning_schedule"
            )
        if "conditioning_required" in details and isinstance(details["conditioning_required"], bool):
            conditioning_required = details["conditioning_required"]
        elif (
            conditioning_mode is not None
            or conditioning_temperature_c is not None
            or conditioning_duration_minutes is not None
        ):
            conditioning_required = True
        else:
            conditioning_required = False

    ingredient_rows = _ordered_fermentation_additions(db, recipe_version.id)
    additions: list[dict[str, Any]] = []
    for row in ingredient_rows:
        stable_source = f"recipe_ingredient:{row.id}"
        template_id = phase4_requirement_template_id(
            recipe_version.id, "PLANNED_ADDITION", stable_source
        )
        additions.append(
            {
                "source_recipe_ingredient_id": str(row.id),
                "ingredient_id": str(row.ingredient_id),
                "ingredient_lot_id": None
                if row.ingredient_lot_id is None
                else str(row.ingredient_lot_id),
                "amount": str(row.amount),
                "unit": row.unit,
                "use_stage": row.use_stage,
                "timing_minutes": row.timing_minutes,
                "stable_source": stable_source,
                "requirement_template_id": str(template_id),
            }
        )

    templates = _build_requirement_templates(
        recipe_version.id,
        fermentation_temperature_status=fermentation_temperature_status,
        required_ph=required_ph,
        conditioning_required=conditioning_required,
        conditioning_temperature_c=conditioning_temperature_c,
        conditioning_duration_minutes=conditioning_duration_minutes,
        apparent_attenuation=recipe_version.apparent_attenuation,
        additions=additions,
    )

    return FermentationLogicalPlan(
        plan_kind=PLAN_KIND_DEFAULT,
        steps=_default_steps(),
        additions=tuple(additions),
        requirement_templates=tuple(templates),
        fermentation_temperature_c=fermentation_temperature_c,
        fermentation_temperature_status=fermentation_temperature_status,
        fermentation_duration_minutes=fermentation_duration_minutes,
        conditioning_required=conditioning_required,
        conditioning_mode=conditioning_mode,
        conditioning_duration_minutes=conditioning_duration_minutes,
        conditioning_temperature_c=conditioning_temperature_c,
        temperature_tolerance_c=str(temperature_tolerance_c),
        temperature_tolerance_provenance=temperature_tolerance_provenance,
        schedule=schedule,
        conditioning_schedule=conditioning_schedule,
        required_ph=required_ph,
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
    conditioning_required: bool | None = None,
    conditioning_mode: str | None = None,
    conditioning_duration_minutes: int | None = None,
    conditioning_temperature_c: str | None = None,
    temperature_tolerance_c: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "materialization_rule_version": MATERIALIZATION_RULE_VERSION,
        "plan_kind": plan.plan_kind,
        "conditioning_required": (
            plan.conditioning_required if conditioning_required is None else conditioning_required
        ),
        "conditioning_mode": plan.conditioning_mode
        if conditioning_mode is None
        else conditioning_mode,
        "conditioning_duration_minutes": plan.conditioning_duration_minutes
        if conditioning_duration_minutes is None
        else conditioning_duration_minutes,
        "conditioning_temperature_c": plan.conditioning_temperature_c
        if conditioning_temperature_c is None
        else conditioning_temperature_c,
        "temperature_tolerance_c": plan.temperature_tolerance_c
        if temperature_tolerance_c is None
        else temperature_tolerance_c,
        "temperature_tolerance_provenance": plan.temperature_tolerance_provenance,
        "fermentation_temperature_c": plan.fermentation_temperature_c,
        "fermentation_temperature_status": plan.fermentation_temperature_status,
        "fermentation_duration_minutes": plan.fermentation_duration_minutes,
        "required_ph": plan.required_ph,
        "schedule": None if plan.schedule is None else list(plan.schedule),
        "conditioning_schedule": None
        if plan.conditioning_schedule is None
        else list(plan.conditioning_schedule),
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
        "requirement_templates": list(plan.requirement_templates),
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
