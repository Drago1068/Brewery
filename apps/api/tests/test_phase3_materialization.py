import uuid
from decimal import Decimal

import pytest

from brewing_api.domain.brew_day.identities import plan_step_id
from brewing_api.domain.brew_day.materialization import (
    AdditionRepeatDeclaration,
    PlanMaterializationError,
    RecipePlanSource,
    SourceAddition,
    SourceStep,
    materialize_phase3_plan,
)


def _source(**overrides) -> RecipePlanSource:
    recipe_id = uuid.uuid4()
    mash_id = uuid.uuid4()
    boil_id = uuid.uuid4()
    defaults = dict(
        recipe_version_id=recipe_id,
        has_phase2_snapshot=True,
        boil_duration_minutes=60,
        planned_mash_duration_minutes=60,
        target_mash_temperature=Decimal("67.0"),
        mash_temperature_unit="degC",
        target_mash_ph=Decimal("5.30"),
        mash_ph_tolerance=Decimal("0.05"),
        target_mash_gravity=Decimal("1.050"),
        mash_gravity_tolerance=Decimal("0.003"),
        batch_size_liters=Decimal("20"),
        target_og=Decimal("1.052"),
        steps=(
            SourceStep(mash_id, "MASH", 1, "Mash", 60, Decimal("67"), {}),
            SourceStep(boil_id, "BOIL", 2, "Boil", 60, None, {}),
        ),
        additions=(),
        fermentable_present=True,
    )
    defaults.update(overrides)
    return RecipePlanSource(**defaults)


def test_legacy_plan_is_mash_then_brew_complete():
    source = _source(has_phase2_snapshot=False, steps=(), fermentable_present=False)
    plan = materialize_phase3_plan(source)
    assert plan.plan_kind == "LEGACY_MASH_ONLY"
    assert [step.canonical_stage_type for step in plan.steps] == ["MASH", "BREW_COMPLETE"]
    assert materialize_phase3_plan(source).logical_plan_hash == plan.logical_plan_hash


def test_first_mash_expands_to_mash_in_and_mash_with_distinct_plan_ids():
    source = _source()
    plan = materialize_phase3_plan(source)
    mash_in = next(step for step in plan.steps if step.canonical_stage_type == "MASH_IN")
    mash = next(step for step in plan.steps if step.canonical_stage_type == "MASH")
    assert mash_in.source_process_step_id == mash.source_process_step_id
    assert mash_in.plan_step_id != mash.plan_step_id
    assert mash_in.expansion_rank == 0
    assert mash.expansion_rank == 1
    types = [step.canonical_stage_type for step in plan.steps]
    assert types.index("MASH_IN") < types.index("MASH") < types.index("BOIL")
    assert types[-1] == "BREW_COMPLETE"


def test_plan_ids_are_byte_identical_across_repeat_materialization():
    source = _source()
    first = materialize_phase3_plan(source)
    second = materialize_phase3_plan(source)
    assert [step.plan_step_id for step in first.steps] == [
        step.plan_step_id for step in second.steps
    ]
    assert first.logical_plan_hash == second.logical_plan_hash


def test_decreasing_canonical_order_fails_closed():
    mash_id = uuid.uuid4()
    boil_id = uuid.uuid4()
    source = _source(
        steps=(
            SourceStep(boil_id, "BOIL", 0, "Boil first", 60, None, {}),
            SourceStep(mash_id, "MASH", 1, "Mash later", 60, None, {}),
        )
    )
    with pytest.raises(PlanMaterializationError) as error:
        materialize_phase3_plan(source)
    assert error.value.code == "PLAN_MATERIALIZATION_FAILED"
    assert any(item["reason"] == "IRRECONCILABLE_SOURCE_ORDER" for item in error.value.failures)


def test_duplicate_sequence_fails_before_session_creation():
    mash_id = uuid.uuid4()
    other = uuid.uuid4()
    source = _source(
        steps=(
            SourceStep(mash_id, "MASH", 1, "Mash", 60, None, {}),
            SourceStep(other, "BOIL", 1, "Boil", 60, None, {}),
        )
    )
    with pytest.raises(PlanMaterializationError):
        materialize_phase3_plan(source)


def test_safe_default_addition_policy_is_planned_occurrences_only():
    addition_id = uuid.uuid4()
    source = _source(
        additions=(
            SourceAddition(
                id=addition_id,
                ingredient_id=uuid.uuid4(),
                amount=Decimal("28"),
                unit="g",
                use_stage="BOIL",
                timing_minutes=60,
            ),
        )
    )
    plan = materialize_phase3_plan(source)
    boil = next(step for step in plan.steps if step.canonical_stage_type == "BOIL")
    assert boil.additions[0]["addition_repeat_policy"] == "PLANNED_OCCURRENCES_ONLY"
    assert boil.additions[0]["assignment_provenance"] == "PHASE2_SAFE_DEFAULT"
    assert boil.additions[0]["timing_basis"] == "BEFORE_PLANNED_STAGE_END"
    assert boil.additions[0]["timing_offset_seconds"] == 3600


def test_runtime_repeat_requires_explicit_declaration_and_preview_hash():
    addition_id = uuid.uuid4()
    source = _source(
        additions=(
            SourceAddition(
                id=addition_id,
                ingredient_id=uuid.uuid4(),
                amount=Decimal("28"),
                unit="g",
                use_stage="MASH",
                timing_minutes=0,
            ),
        )
    )
    preview = materialize_phase3_plan(source)
    mash = next(step for step in preview.steps if step.canonical_stage_type == "MASH")
    declared = materialize_phase3_plan(
        source,
        (
            AdditionRepeatDeclaration(
                source_addition_id=addition_id,
                target_plan_step_id=mash.plan_step_id,
                policy="RUNTIME_REPEAT_ALLOWED",
                reason="Authorized mash hop for rest repeats",
            ),
        ),
        preview.preview_hash,
    )
    mash_declared = next(step for step in declared.steps if step.canonical_stage_type == "MASH")
    assert mash_declared.additions[0]["addition_repeat_policy"] == "RUNTIME_REPEAT_ALLOWED"
    assert declared.logical_plan_hash != preview.logical_plan_hash


def test_plan_step_identity_uses_canonical_inputs():
    recipe = uuid.UUID("11111111-1111-1111-1111-111111111111")
    source = uuid.UUID("22222222-2222-2222-2222-222222222222")
    first = plan_step_id(recipe, "EXPLICIT", str(source), "MASH_IN", 0, 1)
    second = plan_step_id(recipe, "EXPLICIT", str(source), "MASH", 1, 1)
    assert first != second
    assert first == plan_step_id(recipe, "EXPLICIT", str(source).upper(), "MASH_IN", 0, 1)
