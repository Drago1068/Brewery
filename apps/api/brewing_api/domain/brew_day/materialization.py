from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from brewing_api.application.errors import ValidationConflictError
from brewing_api.domain.brew_day.canonical import canonical_uuid, logical_plan_hash
from brewing_api.domain.brew_day.constants import (
    ADDITION_REPEAT_POLICY_VERSION,
    CANONICAL_STAGE_RANK,
    CANONICAL_STAGES,
    MATERIALIZATION_RULE_VERSION,
    NULL_SEQUENCE,
    OPTIONAL_STAGES,
    SOURCE_KIND_RANK,
    SUPPORTED_STEP_TYPES,
)
from brewing_api.domain.brew_day.identities import plan_step_id, requirement_template_id


class PlanMaterializationError(ValidationConflictError):
    def __init__(
        self, message: str, failures: list[dict], code: str = "PLAN_MATERIALIZATION_FAILED"
    ):
        super().__init__(message, code=code, extra={"failures": failures})
        self.failures = failures


@dataclass(frozen=True)
class SourceStep:
    id: UUID
    step_type: str
    sequence: int
    name: str
    duration_minutes: int | None
    temperature_c: Decimal | None
    details: dict[str, Any]


@dataclass(frozen=True)
class SourceAddition:
    id: UUID
    ingredient_id: UUID
    amount: Decimal
    unit: str
    use_stage: str
    timing_minutes: int | None
    ingredient_lot_id: UUID | None = None
    notes: str | None = None
    category: str | None = None
    brew_day_item: bool = False
    governing_stage: str | None = None


@dataclass(frozen=True)
class AdditionRepeatDeclaration:
    source_addition_id: UUID
    target_plan_step_id: UUID
    policy: str
    reason: str


@dataclass(frozen=True)
class RecipePlanSource:
    recipe_version_id: UUID
    has_phase2_snapshot: bool
    boil_duration_minutes: int | None
    planned_mash_duration_minutes: int
    target_mash_temperature: Decimal
    mash_temperature_unit: str
    target_mash_ph: Decimal
    mash_ph_tolerance: Decimal
    target_mash_gravity: Decimal
    mash_gravity_tolerance: Decimal
    batch_size_liters: Decimal | None
    target_og: Decimal | None
    steps: tuple[SourceStep, ...]
    additions: tuple[SourceAddition, ...]
    fermentable_present: bool
    total_liquor_liters: Decimal | None = None


@dataclass
class MappedExplicit:
    source: SourceStep
    canonical_stage_type: str
    expansion_rank: int
    source_kind: str = "EXPLICIT"


@dataclass
class DraftStep:
    canonical_stage_type: str
    source_kind: str
    stable_source_discriminator: str
    source_process_step_id: UUID | None
    expansion_rank: int
    source_sequence: int
    required: bool
    planned_duration_seconds: int | None
    clock_basis: str
    provenance_note: str
    planned_same_type_ordinal: int = 0
    plan_step_id: UUID | None = None
    predecessor_plan_step_id: UUID | None = None
    measurements: list[dict[str, Any]] = field(default_factory=list)
    additions: list[dict[str, Any]] = field(default_factory=list)
    reminders: list[dict[str, Any]] = field(default_factory=list)
    checklists: list[dict[str, Any]] = field(default_factory=list)
    instructions: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class LogicalPlan:
    rule_version: str
    plan_kind: str
    recipe_version_id: UUID
    steps: tuple[DraftStep, ...]
    exclusions: tuple[dict[str, Any], ...]
    preview_hash: str
    logical_plan_hash: str
    addition_assignments: tuple[dict[str, Any], ...]


def _fail(
    failures: list[dict[str, Any]],
    message: str = "Execution plan could not be materialized",
    code: str = "PLAN_MATERIALIZATION_FAILED",
) -> None:
    raise PlanMaterializationError(message, failures, code=code)


def _validate_steps(source: RecipePlanSource) -> list[SourceStep]:
    failures: list[dict[str, Any]] = []
    seen_seq: set[int] = set()
    seen_ids: set[UUID] = set()
    valid: list[SourceStep] = []
    for step in source.steps:
        if not isinstance(step.sequence, int) or step.sequence < 0:
            failures.append(
                {
                    "source_process_step_id": str(step.id),
                    "reason": "INVALID_SEQUENCE",
                    "value": step.sequence,
                }
            )
            continue
        if step.sequence in seen_seq:
            failures.append(
                {
                    "source_process_step_id": str(step.id),
                    "reason": "DUPLICATE_SEQUENCE",
                    "value": step.sequence,
                }
            )
            continue
        if step.id in seen_ids:
            failures.append(
                {"source_process_step_id": str(step.id), "reason": "DUPLICATE_SOURCE_UUID"}
            )
            continue
        if step.step_type not in SUPPORTED_STEP_TYPES:
            failures.append(
                {
                    "source_process_step_id": str(step.id),
                    "reason": "UNSUPPORTED_STEP_TYPE",
                    "value": step.step_type,
                }
            )
            continue
        override = None
        if isinstance(step.details, dict):
            override = step.details.get("phase3_stage")
        if override is not None and override not in CANONICAL_STAGES:
            failures.append(
                {
                    "source_process_step_id": str(step.id),
                    "reason": "UNSUPPORTED_PHASE3_STAGE_OVERRIDE",
                    "value": override,
                }
            )
            continue
        if override is not None and not isinstance(override, str):
            failures.append(
                {
                    "source_process_step_id": str(step.id),
                    "reason": "MALFORMED_ORDERING_FIELD",
                    "value": override,
                }
            )
            continue
        seen_seq.add(step.sequence)
        seen_ids.add(step.id)
        valid.append(step)
    if failures:
        _fail(failures)
    return sorted(valid, key=lambda item: (item.sequence, str(item.id)))


def _map_explicit(steps: list[SourceStep]) -> tuple[list[MappedExplicit], list[dict[str, Any]]]:
    mapped: list[MappedExplicit] = []
    exclusions: list[dict[str, Any]] = []
    first_mash_seen = False
    for step in steps:
        override = step.details.get("phase3_stage") if isinstance(step.details, dict) else None
        if step.step_type == "PACKAGING_FOUNDATION" and not override:
            exclusions.append(
                {
                    "source_process_step_id": canonical_uuid(step.id),
                    "reason": "PACKAGING_FOUNDATION_EXCLUDED",
                }
            )
            continue
        if step.step_type == "FERMENTATION_FOUNDATION" and not override:
            exclusions.append(
                {
                    "source_process_step_id": canonical_uuid(step.id),
                    "reason": "FERMENTATION_FOUNDATION_PITCH_PROVENANCE_ONLY",
                }
            )
            continue
        if override:
            mapped.append(MappedExplicit(step, override, 0))
            continue
        if step.step_type == "MASH":
            if not first_mash_seen:
                mapped.append(MappedExplicit(step, "MASH_IN", 0))
                mapped.append(MappedExplicit(step, "MASH", 1))
                first_mash_seen = True
            else:
                mapped.append(MappedExplicit(step, "MASH", 0))
            continue
        if step.step_type == "BOIL":
            mapped.append(MappedExplicit(step, "BOIL", 0))
            continue
        _fail(
            [
                {
                    "source_process_step_id": str(step.id),
                    "reason": "UNSUPPORTED_STEP_TYPE",
                    "value": step.step_type,
                }
            ]
        )
    previous_rank = -1
    previous_seq = -1
    for item in mapped:
        rank = CANONICAL_STAGE_RANK[item.canonical_stage_type]
        if item.source.sequence > previous_seq and previous_seq >= 0 and rank < previous_rank:
            _fail(
                [
                    {
                        "source_process_step_id": str(item.source.id),
                        "reason": "IRRECONCILABLE_SOURCE_ORDER",
                        "canonical_stage": item.canonical_stage_type,
                    }
                ]
            )
        if item.source.sequence != previous_seq:
            previous_rank = rank
            previous_seq = item.source.sequence
        else:
            previous_rank = max(previous_rank, rank)
    return mapped, exclusions


def _draft_from_mapped(item: MappedExplicit, required: bool) -> DraftStep:
    duration = None
    if item.canonical_stage_type in {"MASH", "BOIL"} and item.source.duration_minutes is not None:
        duration = item.source.duration_minutes * 60
    return DraftStep(
        canonical_stage_type=item.canonical_stage_type,
        source_kind="EXPLICIT",
        stable_source_discriminator=canonical_uuid(item.source.id),
        source_process_step_id=item.source.id,
        expansion_rank=item.expansion_rank,
        source_sequence=item.source.sequence,
        required=required,
        planned_duration_seconds=duration,
        clock_basis="WALL_CLOCK",
        provenance_note="EXPLICIT_PROCESS_STEP",
    )


def _default_step(stage: str, required: bool, key: str, duration: int | None = None) -> DraftStep:
    kind = "PHASE3_DEFAULT"
    if stage == "BREW_COMPLETE":
        kind = "DERIVED_CONDITIONAL"
        key = "derived:BREW_COMPLETE"
    if stage == "MASH_IN":
        kind = "DERIVED_CONDITIONAL"
    return DraftStep(
        canonical_stage_type=stage,
        source_kind=kind,
        stable_source_discriminator=key,
        source_process_step_id=None,
        expansion_rank=0,
        source_sequence=NULL_SEQUENCE,
        required=required,
        planned_duration_seconds=duration,
        clock_basis="WALL_CLOCK",
        provenance_note=kind,
    )


def _occupied(drafts: list[DraftStep], stage: str) -> bool:
    return any(item.canonical_stage_type == stage for item in drafts)


def _insert_defaults(
    source: RecipePlanSource,
    drafts: list[DraftStep],
    whirlpool_needed: bool,
    mash_source_id: UUID | None,
) -> list[DraftStep]:
    extras: list[DraftStep] = []
    if not _occupied(drafts, "PRE_BREW"):
        extras.append(_default_step("PRE_BREW", True, "default:PRE_BREW"))
    if not _occupied(drafts, "WATER_PREPARATION"):
        extras.append(_default_step("WATER_PREPARATION", True, "default:WATER_PREPARATION"))
    if source.fermentable_present and not _occupied(drafts, "MILLING"):
        extras.append(_default_step("MILLING", False, "default:MILLING"))
    if not _occupied(drafts, "MASH"):
        extras.append(
            _default_step(
                "MASH",
                True,
                "default:MASH",
                source.planned_mash_duration_minutes * 60,
            )
        )
    occupied = drafts + extras
    if any(item.canonical_stage_type == "MASH" for item in occupied) and not any(
        item.canonical_stage_type == "MASH_IN" for item in occupied
    ):
        discriminator = canonical_uuid(mash_source_id) if mash_source_id else "derived:MASH_IN"
        extras.append(
            DraftStep(
                canonical_stage_type="MASH_IN",
                source_kind="DERIVED_CONDITIONAL",
                stable_source_discriminator=discriminator,
                source_process_step_id=mash_source_id,
                expansion_rank=0,
                source_sequence=NULL_SEQUENCE,
                required=True,
                planned_duration_seconds=None,
                clock_basis="WALL_CLOCK",
                provenance_note="DERIVED_FROM_MASH",
            )
        )
    if not _occupied(drafts, "LAUTER_SPARGE"):
        extras.append(_default_step("LAUTER_SPARGE", False, "default:LAUTER_SPARGE"))
    if not _occupied(drafts, "PRE_BOIL"):
        extras.append(_default_step("PRE_BOIL", True, "default:PRE_BOIL"))
    if not _occupied(drafts, "BOIL"):
        if source.boil_duration_minutes is None:
            _fail([{"reason": "MISSING_BOIL_DURATION", "rule": "BOIL"}])
        extras.append(
            _default_step("BOIL", True, "default:BOIL", source.boil_duration_minutes * 60)
        )
    if whirlpool_needed and not _occupied(drafts, "WHIRLPOOL_FLAMEOUT"):
        extras.append(_default_step("WHIRLPOOL_FLAMEOUT", True, "derived:WHIRLPOOL_FLAMEOUT"))
        extras[-1].source_kind = "DERIVED_CONDITIONAL"
        extras[-1].provenance_note = "DERIVED_CONDITIONAL"
    if not _occupied(drafts, "CHILL"):
        extras.append(_default_step("CHILL", True, "default:CHILL"))
    if not _occupied(drafts, "TRANSFER"):
        extras.append(_default_step("TRANSFER", True, "default:TRANSFER"))
    if not _occupied(drafts, "YEAST_PITCH"):
        extras.append(_default_step("YEAST_PITCH", True, "default:YEAST_PITCH"))
    if not _occupied(drafts, "BREW_COMPLETE"):
        extras.append(_default_step("BREW_COMPLETE", True, "derived:BREW_COMPLETE"))
    return drafts + extras


def _finalize_order(recipe_version_id: UUID, drafts: list[DraftStep]) -> list[DraftStep]:
    drafts.sort(
        key=lambda item: (
            CANONICAL_STAGE_RANK[item.canonical_stage_type],
            SOURCE_KIND_RANK[item.source_kind],
            item.source_sequence,
            item.expansion_rank,
            item.stable_source_discriminator,
        )
    )
    ordinals: dict[str, int] = {}
    seen_ids: set[UUID] = set()
    for item in drafts:
        ordinals[item.canonical_stage_type] = ordinals.get(item.canonical_stage_type, 0) + 1
        item.planned_same_type_ordinal = ordinals[item.canonical_stage_type]
        item.plan_step_id = plan_step_id(
            recipe_version_id,
            item.source_kind,
            item.stable_source_discriminator,
            item.canonical_stage_type,
            item.expansion_rank,
            item.planned_same_type_ordinal,
        )
        if item.plan_step_id in seen_ids:
            _fail(
                [
                    {
                        "reason": "PLAN_STEP_ID_COLLISION",
                        "plan_step_id": str(item.plan_step_id),
                        "canonical_stage": item.canonical_stage_type,
                    }
                ],
                message="Duplicate derived plan identity",
                code="PLAN_STEP_ID_COLLISION",
            )
        seen_ids.add(item.plan_step_id)
    for index, item in enumerate(drafts):
        item.predecessor_plan_step_id = drafts[index - 1].plan_step_id if index else None
    return drafts


def _measurement(
    plan_id: UUID,
    key: str,
    measurement_type: str,
    process_point: str,
    unit: str,
    required: bool,
    waivable: bool,
    runtime_policy: str,
    target: Decimal | None = None,
    tolerance: Decimal | None = None,
) -> dict[str, Any]:
    template_id = requirement_template_id(plan_id, "MEASUREMENT", key)
    return {
        "requirement_template_id": canonical_uuid(template_id),
        "requirement_class": "MEASUREMENT",
        "definition_key": key,
        "measurement_type": measurement_type,
        "process_point": process_point,
        "canonical_unit": unit,
        "required": required,
        "waivable": waivable,
        "runtime_occurrence_policy": runtime_policy,
        "target_value": str(target) if target is not None else None,
        "tolerance": str(tolerance) if tolerance is not None else None,
        "rule_version": "phase3-measurement-v1",
    }


def _checklist(
    plan_id: UUID, key: str, label: str, required: bool, waivable: bool, runtime_policy: str
) -> dict[str, Any]:
    template_id = requirement_template_id(plan_id, "CHECKLIST", key)
    return {
        "requirement_template_id": canonical_uuid(template_id),
        "requirement_class": "CHECKLIST",
        "definition_key": key,
        "label": label,
        "required": required,
        "waivable": waivable,
        "runtime_occurrence_policy": runtime_policy,
    }


def _attach_stage_requirements(source: RecipePlanSource, step: DraftStep, legacy: bool) -> None:
    assert step.plan_step_id is not None
    plan_id = step.plan_step_id
    stage = step.canonical_stage_type
    regenerate = "REGENERATE_FROM_RULE"
    if stage == "PRE_BREW":
        step.checklists.append(
            _checklist(
                plan_id, "SNAPSHOT_RECEIPT", "Confirm plan snapshot", True, False, "DO_NOT_COPY"
            )
        )
        step.checklists.append(
            _checklist(plan_id, "PREFLIGHT", "Preflight complete", True, False, "DO_NOT_COPY")
        )
    elif stage == "WATER_PREPARATION":
        step.checklists.append(
            _checklist(plan_id, "LIQUOR_READY", "Liquor prepared to plan", True, True, regenerate)
        )
    elif stage == "MILLING":
        step.checklists.append(
            _checklist(plan_id, "MILLING_DONE", "Grain milled", False, True, regenerate)
        )
    elif stage == "MASH_IN":
        target = source.target_mash_temperature
        step.measurements.append(
            _measurement(
                plan_id,
                "MASH_IN_TEMPERATURE",
                "MASH_IN_TEMPERATURE",
                "MASH_IN",
                "degC",
                True,
                True,
                regenerate,
                target,
                Decimal("2.0"),
            )
        )
    elif stage == "MASH":
        if legacy:
            step.measurements.append(
                _measurement(
                    plan_id,
                    "MASH_PH",
                    "MASH_PH",
                    "MASH",
                    "pH",
                    True,
                    False,
                    regenerate,
                    source.target_mash_ph,
                    source.mash_ph_tolerance,
                )
            )
            step.measurements.append(
                _measurement(
                    plan_id,
                    "MASH_GRAVITY",
                    "MASH_GRAVITY",
                    "MASH",
                    "SG",
                    True,
                    False,
                    regenerate,
                    source.target_mash_gravity,
                    source.mash_gravity_tolerance,
                )
            )
        else:
            step.measurements.append(
                _measurement(
                    plan_id,
                    "MASH_REST_TEMPERATURE",
                    "MASH_REST_TEMPERATURE",
                    "MASH",
                    "degC",
                    True,
                    True,
                    regenerate,
                    source.target_mash_temperature,
                    Decimal("2.0"),
                )
            )
            step.measurements.append(
                _measurement(
                    plan_id,
                    "MASH_PH",
                    "MASH_PH",
                    "MASH",
                    "pH",
                    True,
                    True,
                    regenerate,
                    source.target_mash_ph,
                    source.mash_ph_tolerance,
                )
            )
            step.measurements.append(
                _measurement(
                    plan_id,
                    "POST_MASH_GRAVITY",
                    "POST_MASH_GRAVITY",
                    "POST_MASH",
                    "SG",
                    True,
                    True,
                    regenerate,
                    source.target_mash_gravity,
                    source.mash_gravity_tolerance,
                )
            )
    elif stage == "PRE_BOIL":
        step.measurements.append(
            _measurement(
                plan_id,
                "PRE_BOIL_GRAVITY",
                "PRE_BOIL_GRAVITY",
                "PRE_BOIL",
                "SG",
                True,
                True,
                regenerate,
                source.target_og,
                Decimal("0.003"),
            )
        )
        step.measurements.append(
            _measurement(
                plan_id,
                "PRE_BOIL_VOLUME",
                "PRE_BOIL_VOLUME",
                "PRE_BOIL",
                "L",
                True,
                True,
                regenerate,
                source.batch_size_liters,
                None,
            )
        )
    elif stage == "CHILL":
        step.measurements.append(
            _measurement(
                plan_id,
                "KNOCKOUT_TEMPERATURE",
                "KNOCKOUT_TEMPERATURE",
                "KNOCKOUT",
                "degC",
                True,
                True,
                regenerate,
            )
        )
    elif stage == "TRANSFER":
        step.measurements.append(
            _measurement(
                plan_id,
                "KNOCKOUT_VOLUME",
                "KNOCKOUT_VOLUME",
                "KNOCKOUT",
                "L",
                True,
                True,
                regenerate,
                source.batch_size_liters,
            )
        )
    elif stage == "YEAST_PITCH":
        step.measurements.append(
            _measurement(
                plan_id,
                "PITCH_TEMPERATURE",
                "PITCH_TEMPERATURE",
                "PITCH",
                "degC",
                True,
                False,
                regenerate,
            )
        )
        step.checklists.append(
            _checklist(
                plan_id,
                "YEAST_ADDITION_FACT",
                "Record yeast-pitch addition fact",
                True,
                False,
                "DO_NOT_COPY",
            )
        )
    for measurement in step.measurements:
        reminder_id = requirement_template_id(
            plan_id, "REMINDER", f"{measurement['definition_key']}_REMINDER"
        )
        step.reminders.append(
            {
                "requirement_template_id": canonical_uuid(reminder_id),
                "requirement_class": "REMINDER",
                "definition_key": f"{measurement['definition_key']}_REMINDER",
                "linked_requirement_template_id": measurement["requirement_template_id"],
                "priority": "REQUIRED" if measurement["required"] else "OPTIONAL",
                "required": measurement["required"],
                "waivable": measurement["waivable"],
                "runtime_occurrence_policy": measurement["runtime_occurrence_policy"],
            }
        )


def _stage_duration(steps: list[DraftStep], stage: str) -> int | None:
    matches = [item for item in steps if item.canonical_stage_type == stage]
    if len(matches) == 1:
        return matches[0].planned_duration_seconds
    return None


def _unambiguous_step(steps: list[DraftStep], stage: str) -> DraftStep | None:
    matches = [item for item in steps if item.canonical_stage_type == stage]
    if len(matches) == 1:
        return matches[0]
    return None


def _map_additions(
    source: RecipePlanSource, steps: list[DraftStep]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    assignments: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    whirlpool_needed = False
    for addition in source.additions:
        use = addition.use_stage
        timing = addition.timing_minutes
        if use in {"FERMENTATION", "DRY_HOP", "PACKAGING"}:
            exclusions.append(
                {
                    "source_addition_id": canonical_uuid(addition.id),
                    "reason": "EXCLUDED_POST_PITCH_ADDITION",
                    "use_stage": use,
                }
            )
            continue
        if use == "WHIRLPOOL" or (use == "BOIL" and timing == 0):
            if use == "WHIRLPOOL":
                whirlpool_needed = True
        basis: str
        offset: int | None
        clock = "WALL_CLOCK"
        stage_name: str
        if use == "FIRST_WORT":
            stage_name = "LAUTER_SPARGE"
            basis = "AT_STAGE_START"
            if timing not in (None, 0):
                _fail(
                    [
                        {
                            "source_addition_id": str(addition.id),
                            "reason": "INVALID_FIRST_WORT_OFFSET",
                            "value": timing,
                        }
                    ]
                )
            offset = 0
        elif use == "MASH":
            stage_name = "MASH"
            if timing in (None, 0):
                basis = "AT_STAGE_START"
                offset = 0
            else:
                basis = "FROM_STAGE_START"
                offset = timing * 60
                duration = _stage_duration(steps, "MASH")
                if duration is not None and offset > duration:
                    _fail(
                        [
                            {
                                "source_addition_id": str(addition.id),
                                "reason": "MASH_ADDITION_EXCEEDS_DURATION",
                                "offset_seconds": offset,
                            }
                        ]
                    )
        elif use == "BOIL":
            stage_name = "BOIL"
            duration = _stage_duration(steps, "BOIL")
            if timing is None:
                _fail(
                    [
                        {
                            "source_addition_id": str(addition.id),
                            "reason": "MISSING_BOIL_TIMING",
                        }
                    ]
                )
            if timing < 0:
                _fail(
                    [
                        {
                            "source_addition_id": str(addition.id),
                            "reason": "NEGATIVE_TIMING",
                            "value": timing,
                        }
                    ]
                )
            if duration is not None and timing * 60 > duration:
                _fail(
                    [
                        {
                            "source_addition_id": str(addition.id),
                            "reason": "BOIL_ADDITION_EXCEEDS_DURATION",
                            "value": timing,
                        }
                    ]
                )
            if timing == 0:
                basis = "AT_PLANNED_STAGE_END"
                offset = 0
            else:
                basis = "BEFORE_PLANNED_STAGE_END"
                offset = timing * 60
        elif use == "WHIRLPOOL":
            stage_name = "WHIRLPOOL_FLAMEOUT"
            basis = "FROM_STAGE_START"
            offset = 0 if timing is None else timing * 60
            whirlpool_needed = True
        elif use == "MISCELLANEOUS":
            if not addition.brew_day_item or not addition.governing_stage:
                _fail(
                    [
                        {
                            "source_addition_id": str(addition.id),
                            "reason": "UNSUPPORTED_ADDITION_CONTEXT",
                            "use_stage": use,
                        }
                    ]
                )
            stage_name = addition.governing_stage
            basis = "UNSCHEDULED"
            offset = None
            clock = "WALL_CLOCK"
        else:
            _fail(
                [
                    {
                        "source_addition_id": str(addition.id),
                        "reason": "UNSUPPORTED_ADDITION_CONTEXT",
                        "use_stage": use,
                    }
                ]
            )
        owner = _unambiguous_step(steps, stage_name)
        if owner is None:
            _fail(
                [
                    {
                        "source_addition_id": str(addition.id),
                        "reason": "AMBIGUOUS_OR_MISSING_ADDITION_STAGE",
                        "canonical_stage": stage_name,
                    }
                ]
            )
        assert owner.plan_step_id is not None
        template_id = requirement_template_id(
            owner.plan_step_id, "ADDITION", canonical_uuid(addition.id)
        )
        reminder_id = requirement_template_id(
            owner.plan_step_id, "REMINDER", f"ADDITION:{canonical_uuid(addition.id)}"
        )
        assignment = {
            "requirement_template_id": canonical_uuid(template_id),
            "requirement_class": "ADDITION",
            "source_addition_id": canonical_uuid(addition.id),
            "ingredient_id": canonical_uuid(addition.ingredient_id),
            "ingredient_lot_id": (
                canonical_uuid(addition.ingredient_lot_id) if addition.ingredient_lot_id else None
            ),
            "plan_step_id": canonical_uuid(owner.plan_step_id),
            "canonical_stage_type": stage_name,
            "planned_amount": str(addition.amount),
            "planned_unit": addition.unit,
            "timing_basis": basis,
            "timing_offset_seconds": offset,
            "clock_basis": clock,
            "required": True,
            "waivable": True,
            "runtime_occurrence_policy": "DO_NOT_COPY",
            "addition_repeat_policy": "PLANNED_OCCURRENCES_ONLY",
            "addition_repeat_policy_version": ADDITION_REPEAT_POLICY_VERSION,
            "assignment_provenance": "PHASE2_SAFE_DEFAULT",
            "assignment_reason_code": "ABSENT_PHASE3_REPEAT_DECLARATION",
            "notes": addition.notes,
        }
        owner.additions.append(assignment)
        owner.reminders.append(
            {
                "requirement_template_id": canonical_uuid(reminder_id),
                "requirement_class": "REMINDER",
                "definition_key": f"ADDITION:{canonical_uuid(addition.id)}",
                "linked_requirement_template_id": canonical_uuid(template_id),
                "priority": "REQUIRED",
                "required": True,
                "waivable": True,
                "runtime_occurrence_policy": "DO_NOT_COPY",
            }
        )
        assignments.append(assignment)
    return assignments, exclusions, whirlpool_needed


def _apply_declarations(
    assignments: list[dict[str, Any]],
    declarations: tuple[AdditionRepeatDeclaration, ...],
    preview_hash: str,
    supplied_preview_hash: str | None,
) -> None:
    if not declarations:
        return
    if supplied_preview_hash != preview_hash:
        raise ValidationConflictError(
            "Plan preview is stale",
            code="PLAN_PREVIEW_STALE",
            extra={"expected": preview_hash},
        )
    seen: set[tuple[str, str]] = set()
    never_sources: dict[str, str] = {}
    by_pair = {(item["source_addition_id"], item["plan_step_id"]): item for item in assignments}
    for declaration in declarations:
        if declaration.policy not in {
            "NEVER",
            "PLANNED_OCCURRENCES_ONLY",
            "RUNTIME_REPEAT_ALLOWED",
        }:
            raise ValidationConflictError(
                "Invalid addition-repeat policy",
                code="INVALID_ADDITION_REPEAT_POLICY",
            )
        if not (10 <= len(declaration.reason) <= 1000):
            raise ValidationConflictError(
                "Addition-repeat declaration reason must be 10 to 1000 characters",
                code="INVALID_DECLARATION_REASON",
            )
        pair = (
            canonical_uuid(declaration.source_addition_id),
            canonical_uuid(declaration.target_plan_step_id),
        )
        if pair in seen:
            raise ValidationConflictError(
                "Duplicate addition-repeat declaration",
                code="DUPLICATE_DECLARATION",
            )
        seen.add(pair)
        target = by_pair.get(pair)
        if target is None:
            raise ValidationConflictError(
                "Addition-repeat declaration does not match a plan assignment",
                code="UNTRACEABLE_ADDITION_ASSIGNMENT",
                extra={"source_addition_id": pair[0], "plan_step_id": pair[1]},
            )
        if declaration.policy == "NEVER":
            source = pair[0]
            if source in never_sources:
                raise ValidationConflictError(
                    "NEVER policy may be assigned only once",
                    code="NEVER_POLICY_MULTI_ASSIGNMENT",
                )
            never_sources[source] = pair[1]
        target["addition_repeat_policy"] = declaration.policy
        target["assignment_provenance"] = "PHASE3_EXPLICIT_SESSION_PLAN"
        target["assignment_reason_code"] = "EXPLICIT_SESSION_PLAN_DECLARATION"
        target["declaration_reason"] = declaration.reason
        target["runtime_occurrence_policy"] = (
            "REGENERATE_FROM_RULE"
            if declaration.policy == "RUNTIME_REPEAT_ALLOWED"
            else "DO_NOT_COPY"
        )


def _document(
    source: RecipePlanSource, steps: list[DraftStep], exclusions: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "materialization_rule_version": MATERIALIZATION_RULE_VERSION,
        "addition_repeat_policy_version": ADDITION_REPEAT_POLICY_VERSION,
        "recipe_version_id": canonical_uuid(source.recipe_version_id),
        "exclusions": exclusions,
        "steps": [
            {
                "plan_step_id": canonical_uuid(step.plan_step_id) if step.plan_step_id else None,
                "canonical_stage_type": step.canonical_stage_type,
                "required": step.required,
                "source_kind": step.source_kind,
                "source_process_step_id": (
                    canonical_uuid(step.source_process_step_id)
                    if step.source_process_step_id
                    else None
                ),
                "stable_source_discriminator": step.stable_source_discriminator,
                "expansion_rank": step.expansion_rank,
                "planned_same_type_ordinal": step.planned_same_type_ordinal,
                "source_sequence": step.source_sequence,
                "predecessor_plan_step_id": (
                    canonical_uuid(step.predecessor_plan_step_id)
                    if step.predecessor_plan_step_id
                    else None
                ),
                "planned_duration_seconds": step.planned_duration_seconds,
                "clock_basis": step.clock_basis,
                "measurements": step.measurements,
                "additions": step.additions,
                "reminders": step.reminders,
                "checklists": step.checklists,
            }
            for step in steps
        ],
    }


def materialize_legacy_plan(source: RecipePlanSource) -> LogicalPlan:
    mash = DraftStep(
        canonical_stage_type="MASH",
        source_kind="LEGACY_PHASE1A",
        stable_source_discriminator="legacy:MASH",
        source_process_step_id=None,
        expansion_rank=0,
        source_sequence=0,
        required=True,
        planned_duration_seconds=source.planned_mash_duration_minutes * 60,
        clock_basis="WALL_CLOCK",
        provenance_note="LEGACY_PHASE1A",
    )
    complete = DraftStep(
        canonical_stage_type="BREW_COMPLETE",
        source_kind="LEGACY_PHASE1A",
        stable_source_discriminator="legacy:BREW_COMPLETE",
        source_process_step_id=None,
        expansion_rank=0,
        source_sequence=1,
        required=True,
        planned_duration_seconds=None,
        clock_basis="WALL_CLOCK",
        provenance_note="LEGACY_PHASE1A",
    )
    steps = _finalize_order(source.recipe_version_id, [mash, complete])
    for step in steps:
        _attach_stage_requirements(source, step, legacy=True)
    document = _document(source, steps, [])
    digest = logical_plan_hash(document)
    return LogicalPlan(
        rule_version=MATERIALIZATION_RULE_VERSION,
        plan_kind="LEGACY_MASH_ONLY",
        recipe_version_id=source.recipe_version_id,
        steps=tuple(steps),
        exclusions=(),
        preview_hash=digest,
        logical_plan_hash=digest,
        addition_assignments=(),
    )


def materialize_phase3_plan(
    source: RecipePlanSource,
    declarations: tuple[AdditionRepeatDeclaration, ...] = (),
    plan_preview_hash: str | None = None,
) -> LogicalPlan:
    if not source.has_phase2_snapshot:
        return materialize_legacy_plan(source)
    valid_steps = _validate_steps(source)
    mapped, step_exclusions = _map_explicit(valid_steps)
    drafts = [
        _draft_from_mapped(item, item.canonical_stage_type not in OPTIONAL_STAGES)
        for item in mapped
    ]
    mash_source = next(
        (item.source.id for item in mapped if item.canonical_stage_type == "MASH"), None
    )
    for step in drafts:
        if step.canonical_stage_type == "MASH" and step.planned_duration_seconds is None:
            step.planned_duration_seconds = source.planned_mash_duration_minutes * 60
        if step.canonical_stage_type == "BOIL" and step.planned_duration_seconds is None:
            if source.boil_duration_minutes is None:
                _fail(
                    [
                        {
                            "source_process_step_id": str(step.source_process_step_id),
                            "reason": "MISSING_BOIL_DURATION",
                        }
                    ]
                )
            step.planned_duration_seconds = source.boil_duration_minutes * 60
    whirlpool_needed = any(
        item.use_stage == "WHIRLPOOL" or (item.use_stage == "BOIL" and item.timing_minutes == 0)
        for item in source.additions
    )
    drafts = _insert_defaults(source, drafts, whirlpool_needed, mash_source)
    drafts = _finalize_order(source.recipe_version_id, drafts)
    assignments, addition_exclusions, _ = _map_additions(source, drafts)
    # If whirlpool became required from additions after defaults, ensure the stage exists.
    if whirlpool_needed and not _occupied(drafts, "WHIRLPOOL_FLAMEOUT"):
        _fail([{"reason": "WHIRLPOOL_STAGE_MISSING_AFTER_DEFAULTS"}])
    for step in drafts:
        _attach_stage_requirements(source, step, legacy=False)
    exclusions = step_exclusions + addition_exclusions
    preview_doc = _document(source, drafts, exclusions)
    preview_hash = logical_plan_hash(preview_doc)
    _apply_declarations(assignments, declarations, preview_hash, plan_preview_hash)
    snapshot_doc = _document(source, drafts, exclusions)
    snapshot_hash = logical_plan_hash(snapshot_doc)
    return LogicalPlan(
        rule_version=MATERIALIZATION_RULE_VERSION,
        plan_kind="PHASE3_FULL",
        recipe_version_id=source.recipe_version_id,
        steps=tuple(drafts),
        exclusions=tuple(exclusions),
        preview_hash=preview_hash,
        logical_plan_hash=snapshot_hash,
        addition_assignments=tuple(assignments),
    )


def preview_plan(source: RecipePlanSource) -> LogicalPlan:
    return materialize_phase3_plan(source)
