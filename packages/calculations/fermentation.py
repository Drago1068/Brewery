"""Phase 4 deterministic fermentation calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID

from .brewing import ONE, abv, apparent_attenuation
from .units import fahrenheit_to_celsius

ZERO = Decimal("0")
CALCULATION_UNDEFINED = "CALCULATION_UNDEFINED"
NOT_COMPUTED = "NOT_COMPUTED"
STABLE_GRAVITY_SCHEMA_VERSION = "phase4-stable-gravity-v1"
PLATO_ADAPTER_VERSION = "phase4-plato-to-sg-v1"
SPACING_SECONDS = 86400
STABLE_SPREAD_MAX = Decimal("0.002")
SG_MIN = Decimal("0.900")
SG_MAX = Decimal("1.300")
PLATO_RESIDUAL = Decimal("0.0000001")
PLATO_MAX_ITERATIONS = 80


class StableGravityStatus(str, Enum):
    STABLE = "STABLE"
    NOT_STABLE = "NOT_STABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class GravityLeaf:
    measurement_id: UUID
    canonical_sg: Decimal
    observed_at: datetime
    recorded_at: datetime


@dataclass(frozen=True)
class StableGravityEvaluation:
    status: StableGravityStatus
    window_measurement_ids: tuple[UUID, ...]
    spread: Decimal | None
    schema_version: str = STABLE_GRAVITY_SCHEMA_VERSION


def _plato_polynomial(sg: Decimal) -> Decimal:
    # Slice 2 remediation (F-005): coefficients are identical to the shared
    # ``specific_gravity_to_plato`` authority (proven by golden equivalence in
    # ``test_phase4_slice2_remediation.py``). This local form is retained
    # because the shared authority raises below SG 1.000 while this adapter's
    # normative domain is SG 0.900-1.300, so unconditional delegation would
    # change observable results for valid negative-Plato inputs.
    return (
        Decimal("-616.868")
        + Decimal("1111.14") * sg
        - Decimal("630.272") * sg**2
        + Decimal("135.997") * sg**3
    )


def plato_domain_bounds() -> tuple[Decimal, Decimal]:
    return _plato_polynomial(SG_MIN), _plato_polynomial(SG_MAX)


def plato_to_sg(plato: Decimal) -> Decimal:
    plato_min, plato_max = plato_domain_bounds()
    if plato < plato_min or plato > plato_max:
        raise ValueError("PLATO_OUT_OF_DOMAIN")
    low = SG_MIN
    high = SG_MAX
    for _ in range(PLATO_MAX_ITERATIONS):
        mid = (low + high) / 2
        converted = _plato_polynomial(mid)
        residual = abs(converted - plato)
        if residual < PLATO_RESIDUAL:
            return mid
        if converted < plato:
            low = mid
        else:
            high = mid
    raise ValueError("PLATO_CONVERSION_FAILED")


def canonicalize_gravity(raw_value: Decimal, raw_unit: str) -> tuple[Decimal, str | None]:
    if raw_unit == "SG":
        canonical = raw_value
        model_id = None
    elif raw_unit == "Plato":
        canonical = plato_to_sg(raw_value)
        model_id = PLATO_ADAPTER_VERSION
    else:
        raise ValueError("UNSUPPORTED_UNIT")
    if canonical < SG_MIN or canonical > SG_MAX:
        raise ValueError("GRAVITY_OUT_OF_DOMAIN")
    return canonical, model_id


def canonicalize_temperature(raw_value: Decimal, raw_unit: str) -> Decimal:
    if raw_unit == "degC":
        return raw_value
    if raw_unit == "degF":
        return fahrenheit_to_celsius(raw_value)
    raise ValueError("UNSUPPORTED_UNIT")


def stable_gravity_evaluator(leaves: list[GravityLeaf]) -> StableGravityEvaluation:
    ordered = sorted(leaves, key=lambda item: (item.observed_at, item.recorded_at, item.measurement_id))
    if len(ordered) < 3:
        return StableGravityEvaluation(
            status=StableGravityStatus.INSUFFICIENT_EVIDENCE,
            window_measurement_ids=(),
            spread=None,
        )
    window = ordered[-3:]
    for earlier, later in ((window[0], window[1]), (window[1], window[2])):
        delta = (later.observed_at - earlier.observed_at).total_seconds()
        if delta < SPACING_SECONDS:
            return StableGravityEvaluation(
                status=StableGravityStatus.NOT_STABLE,
                window_measurement_ids=tuple(item.measurement_id for item in window),
                spread=None,
            )
    values = [item.canonical_sg for item in window]
    spread = max(values) - min(values)
    status = (
        StableGravityStatus.STABLE
        if spread <= STABLE_SPREAD_MAX
        else StableGravityStatus.NOT_STABLE
    )
    return StableGravityEvaluation(
        status=status,
        window_measurement_ids=tuple(item.measurement_id for item in window),
        spread=spread,
    )


def try_apparent_attenuation_ratio(og: Decimal | None, fg: Decimal | None) -> Decimal | Literal["CALCULATION_UNDEFINED"]:
    if og is None or fg is None:
        return CALCULATION_UNDEFINED
    try:
        return apparent_attenuation(og, fg)
    except ValueError:
        return CALCULATION_UNDEFINED


def try_abv_percent(og: Decimal | None, fg: Decimal | None) -> Decimal | Literal["CALCULATION_UNDEFINED"]:
    if og is None or fg is None:
        return CALCULATION_UNDEFINED
    try:
        return abv(og, fg)
    except ValueError:
        return CALCULATION_UNDEFINED


def fermentation_progress(
    og: Decimal | None,
    current: Decimal | None,
    target_fg: Decimal | None,
) -> Decimal | Literal["CALCULATION_UNDEFINED"]:
    if og is None or current is None or target_fg is None:
        return CALCULATION_UNDEFINED
    denominator = og - target_fg
    if denominator == ZERO or og <= target_fg:
        return CALCULATION_UNDEFINED
    progress = (og - current) / denominator
    if current > og:
        progress = ZERO
    elif current < target_fg:
        progress = ONE
    if progress < ZERO:
        progress = ZERO
    if progress > ONE:
        progress = ONE
    return progress


def final_gravity_from_leaves(
    leaves: list[GravityLeaf],
    stability: StableGravityEvaluation,
) -> Decimal | None:
    if not leaves:
        return None
    ordered = sorted(leaves, key=lambda item: (item.observed_at, item.recorded_at, item.measurement_id))
    if stability.status == StableGravityStatus.STABLE and stability.window_measurement_ids:
        last_id = stability.window_measurement_ids[-1]
        for item in ordered:
            if item.measurement_id == last_id:
                return item.canonical_sg
    return ordered[-1].canonical_sg
