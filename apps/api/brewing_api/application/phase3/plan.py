from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.domain.brew_day.identities import runtime_requirement_id
from brewing_api.domain.brew_day.materialization import (
    AdditionRepeatDeclaration,
    LogicalPlan,
    RecipePlanSource,
    SourceAddition,
    SourceStep,
    materialize_phase3_plan,
)
from brewing_api.domain.brew_day.models import (
    BrewPlanStep,
    BrewRequirementTemplate,
    BrewStageRequirement,
)
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage
from brewing_api.domain.ingredients.models import Ingredient
from brewing_api.domain.recipes.models import RecipeIngredient, RecipeProcessStep, RecipeVersion
from brewing_api.platform.time import utc_now


def recipe_plan_source(db: Session, version: RecipeVersion) -> RecipePlanSource:
    steps = list(
        db.scalars(
            select(RecipeProcessStep)
            .where(RecipeProcessStep.recipe_version_id == version.id)
            .order_by(RecipeProcessStep.sequence, RecipeProcessStep.id)
        ).all()
    )
    additions = list(
        db.scalars(
            select(RecipeIngredient).where(RecipeIngredient.recipe_version_id == version.id)
        ).all()
    )
    fermentable = False
    mapped_additions: list[SourceAddition] = []
    for line in additions:
        ingredient = db.get(Ingredient, line.ingredient_id)
        category = ingredient.category if ingredient else None
        if category == "FERMENTABLE":
            fermentable = True
        details_unscheduled = False
        governing = None
        mapped_additions.append(
            SourceAddition(
                id=line.id,
                ingredient_id=line.ingredient_id,
                amount=line.amount,
                unit=line.unit,
                use_stage=line.use_stage,
                timing_minutes=line.timing_minutes,
                ingredient_lot_id=line.ingredient_lot_id,
                notes=line.notes,
                category=category,
                brew_day_item=details_unscheduled,
                governing_stage=governing,
            )
        )
    liquor = None
    if version.calculation_outputs and isinstance(version.calculation_outputs, dict):
        raw = version.calculation_outputs.get("total_liquor_liters")
        if raw is not None:
            liquor = Decimal(str(raw))
    return RecipePlanSource(
        recipe_version_id=version.id,
        has_phase2_snapshot=version.equipment_snapshot is not None
        or version.calculation_outputs is not None
        or bool(steps),
        boil_duration_minutes=version.boil_duration_minutes,
        planned_mash_duration_minutes=version.planned_mash_duration_minutes,
        target_mash_temperature=version.target_mash_temperature,
        mash_temperature_unit=version.mash_temperature_unit,
        target_mash_ph=version.target_mash_ph,
        mash_ph_tolerance=version.mash_ph_tolerance,
        target_mash_gravity=version.target_mash_gravity,
        mash_gravity_tolerance=version.mash_gravity_tolerance,
        batch_size_liters=version.batch_size_liters,
        target_og=version.target_og,
        steps=tuple(
            SourceStep(
                id=step.id,
                step_type=step.step_type,
                sequence=step.sequence,
                name=step.name,
                duration_minutes=step.duration_minutes,
                temperature_c=step.temperature_c,
                details=step.details or {},
            )
            for step in steps
        ),
        additions=tuple(mapped_additions),
        fermentable_present=fermentable,
        total_liquor_liters=liquor,
    )


def persist_plan(
    db: Session,
    session: BrewSession,
    plan: LogicalPlan,
) -> list[BrewStage]:
    now = utc_now()
    session.plan_kind = plan.plan_kind
    session.materialization_rule_version = plan.rule_version
    session.logical_plan_hash = plan.logical_plan_hash
    session.plan_preview_hash = plan.preview_hash
    session.materialized_at = now
    stages: list[BrewStage] = []
    for index, step in enumerate(plan.steps):
        assert step.plan_step_id is not None
        db.add(
            BrewPlanStep(
                brew_session_id=session.id,
                plan_step_id=step.plan_step_id,
                canonical_stage_type=step.canonical_stage_type,
                required=step.required,
                source_kind=step.source_kind,
                source_process_step_id=step.source_process_step_id,
                stable_source_discriminator=step.stable_source_discriminator,
                expansion_rank=step.expansion_rank,
                planned_same_type_ordinal=step.planned_same_type_ordinal,
                source_sequence=step.source_sequence,
                predecessor_plan_step_id=step.predecessor_plan_step_id,
                planned_duration_seconds=step.planned_duration_seconds,
                clock_basis=step.clock_basis,
                sort_index=index,
                payload={
                    "measurements": step.measurements,
                    "additions": step.additions,
                    "reminders": step.reminders,
                    "checklists": step.checklists,
                },
            )
        )
        templates = (
            [(item, "MEASUREMENT") for item in step.measurements]
            + [(item, "ADDITION") for item in step.additions]
            + [(item, "REMINDER") for item in step.reminders]
            + [(item, "CHECKLIST") for item in step.checklists]
        )
        for payload, cls in templates:
            db.add(
                BrewRequirementTemplate(
                    brew_session_id=session.id,
                    plan_step_id=step.plan_step_id,
                    requirement_template_id=uuid.UUID(payload["requirement_template_id"]),
                    requirement_class=cls,
                    definition_key=payload.get("definition_key")
                    or payload.get("source_addition_id")
                    or cls,
                    required=payload.get("required", True),
                    waivable=payload.get("waivable", True),
                    runtime_occurrence_policy=payload.get(
                        "runtime_occurrence_policy", "REGENERATE_FROM_RULE"
                    ),
                    payload=payload,
                    addition_repeat_policy=payload.get("addition_repeat_policy"),
                    addition_repeat_policy_version=payload.get("addition_repeat_policy_version"),
                    assignment_provenance=payload.get("assignment_provenance"),
                    source_addition_id=(
                        uuid.UUID(payload["source_addition_id"])
                        if payload.get("source_addition_id")
                        else None
                    ),
                )
            )
        stage = BrewStage(
            brew_session_id=session.id,
            name=step.canonical_stage_type,
            status="PENDING",
            target_duration_seconds=step.planned_duration_seconds or 0,
            target_temperature=session.target_mash_temperature,
            temperature_unit=session.mash_temperature_unit,
            target_ph=session.target_mash_ph,
            ph_tolerance=session.mash_ph_tolerance,
            target_gravity=session.target_mash_gravity,
            gravity_tolerance=session.mash_gravity_tolerance,
            plan_step_id=step.plan_step_id,
            canonical_stage_type=step.canonical_stage_type,
            occurrence_number=1,
            required=step.required,
        )
        db.add(stage)
        db.flush()
        _materialize_occurrence_requirements(db, session, stage, "PLANNED")
        stages.append(stage)
    db.flush()
    return stages


def _materialize_occurrence_requirements(
    db: Session,
    session: BrewSession,
    stage: BrewStage,
    provenance: str,
) -> str:
    templates = list(
        db.scalars(
            select(BrewRequirementTemplate).where(
                BrewRequirementTemplate.brew_session_id == session.id,
                BrewRequirementTemplate.plan_step_id == stage.plan_step_id,
            )
        ).all()
    )
    identities: list[str] = []
    for template in templates:
        if provenance != "PLANNED" and template.runtime_occurrence_policy == "DO_NOT_COPY":
            continue
        if (
            provenance != "PLANNED"
            and template.requirement_class == "ADDITION"
            and template.addition_repeat_policy != "RUNTIME_REPEAT_ALLOWED"
        ):
            continue
        requirement_id = runtime_requirement_id(
            stage.id, template.requirement_template_id, template.requirement_class
        )
        db.add(
            BrewStageRequirement(
                brew_session_id=session.id,
                stage_instance_id=stage.id,
                requirement_template_id=template.requirement_template_id,
                requirement_class=template.requirement_class,
                requirement_id=requirement_id,
                required=template.required,
                waivable=template.waivable,
                provenance=provenance,
                payload=template.payload,
            )
        )
        identities.append(str(requirement_id))
    fingerprint = uuid.uuid5(
        uuid.UUID("b3ad9f4c-9e5f-5a31-9df2-25d731f5a302"),
        "phase3-runtime-requirements-v1:" + ",".join(sorted(identities)),
    ).hex
    stage.requirement_set_fingerprint = fingerprint
    return fingerprint


def declarations_from_payload(items: list[dict] | None) -> tuple[AdditionRepeatDeclaration, ...]:
    if not items:
        return ()
    return tuple(
        AdditionRepeatDeclaration(
            source_addition_id=uuid.UUID(str(item["source_addition_id"])),
            target_plan_step_id=uuid.UUID(str(item["target_plan_step_id"])),
            policy=str(item["policy"]),
            reason=str(item["reason"]),
        )
        for item in items
    )


def build_plan(
    db: Session,
    version: RecipeVersion,
    declarations: tuple[AdditionRepeatDeclaration, ...] = (),
    preview_hash: str | None = None,
) -> LogicalPlan:
    return materialize_phase3_plan(recipe_plan_source(db, version), declarations, preview_hash)
