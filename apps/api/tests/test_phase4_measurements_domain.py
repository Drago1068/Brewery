from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from calculations.fermentation import (
    CALCULATION_UNDEFINED,
    GravityLeaf,
    StableGravityStatus,
    canonicalize_gravity,
    fermentation_progress,
    plato_domain_bounds,
    plato_to_sg,
    stable_gravity_evaluator,
    try_abv_percent,
    try_apparent_attenuation_ratio,
)


def _leaf(sg: str, hours: float, measurement_id: UUID | None = None) -> GravityLeaf:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    observed = base + timedelta(hours=hours)
    return GravityLeaf(
        measurement_id=measurement_id or uuid4(),
        canonical_sg=Decimal(sg),
        observed_at=observed,
        recorded_at=observed + timedelta(minutes=1),
    )


def test_stable_gravity_insufficient_with_two_observations():
    result = stable_gravity_evaluator([_leaf("1.010", 0), _leaf("1.010", 24)])
    assert result.status == StableGravityStatus.INSUFFICIENT_EVIDENCE


def test_stable_gravity_stable_equal_triple():
    result = stable_gravity_evaluator(
        [_leaf("1.012", 0), _leaf("1.012", 24), _leaf("1.012", 48)]
    )
    assert result.status == StableGravityStatus.STABLE
    assert result.spread == Decimal("0")


def test_stable_gravity_not_stable_spread_0_004():
    result = stable_gravity_evaluator(
        [_leaf("1.014", 0), _leaf("1.012", 24), _leaf("1.010", 48)]
    )
    assert result.status == StableGravityStatus.NOT_STABLE
    assert result.spread == Decimal("0.004")


def test_stable_gravity_boundary_spread_exactly_0_002():
    result = stable_gravity_evaluator(
        [_leaf("1.014", 0), _leaf("1.013", 24), _leaf("1.012", 48)]
    )
    assert result.status == StableGravityStatus.STABLE
    assert result.spread == Decimal("0.002")


def test_stable_gravity_boundary_spread_0_0020001():
    result = stable_gravity_evaluator(
        [_leaf("1.0140001", 0), _leaf("1.013", 24), _leaf("1.012", 48)]
    )
    assert result.status == StableGravityStatus.NOT_STABLE


def test_stable_gravity_spacing_failure():
    result = stable_gravity_evaluator(
        [
            _leaf("1.012", 0),
            _leaf("1.012", 23 + 59 / 60 + 59 / 3600),
            _leaf("1.012", 48),
        ]
    )
    assert result.status == StableGravityStatus.NOT_STABLE
    assert result.spread is None


def test_stable_gravity_window_uses_last_three_including_newest_disqualifier():
    result = stable_gravity_evaluator(
        [
            _leaf("1.012", 0),
            _leaf("1.012", 24),
            _leaf("1.012", 48),
            _leaf("1.020", 49),
        ]
    )
    assert result.status == StableGravityStatus.NOT_STABLE


def test_plato_out_of_domain_rejects_100_plato():
    with pytest.raises(ValueError, match="PLATO_OUT_OF_DOMAIN"):
        plato_to_sg(Decimal("100"))


def test_plato_round_trip_residual():
    plato_min, plato_max = plato_domain_bounds()
    sg = plato_to_sg((plato_min + plato_max) / 2)
    assert Decimal("0.900") <= sg <= Decimal("1.300")


def test_canonicalize_gravity_plato_adapter():
    sg, model_id = canonicalize_gravity(Decimal("12.5"), "Plato")
    assert model_id == "phase4-plato-to-sg-v1"
    assert Decimal("0.900") <= sg <= Decimal("1.300")


def test_apparent_attenuation_ratio_and_undefined():
    ratio = try_apparent_attenuation_ratio(Decimal("1.050"), Decimal("1.010"))
    assert ratio == Decimal("0.8")
    assert try_apparent_attenuation_ratio(Decimal("1.050"), Decimal("0.990")) == CALCULATION_UNDEFINED
    assert try_abv_percent(Decimal("1.050"), Decimal("1.010")) == Decimal("5.25")


def test_fermentation_progress_clip_and_undefined():
    assert fermentation_progress(Decimal("1.050"), Decimal("1.060"), Decimal("1.010")) == Decimal("0")
    assert fermentation_progress(Decimal("1.050"), Decimal("1.000"), Decimal("1.010")) == Decimal("1")
    assert fermentation_progress(Decimal("1.050"), Decimal("1.030"), Decimal("1.050")) == CALCULATION_UNDEFINED
