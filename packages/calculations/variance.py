from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Comparison:
    target: Decimal
    actual: Decimal
    variance: Decimal
    tolerance: Decimal
    outside_tolerance: bool


def compare_measurement(
    target: Decimal, actual: Decimal, tolerance: Decimal, precision: str = "0.001"
) -> Comparison:
    """Compare an observation with an inclusive absolute tolerance.

    Values are quantized with ROUND_HALF_UP so API, database, and UI results are stable.
    """
    if tolerance < 0:
        raise ValueError("Tolerance cannot be negative")
    quantum = Decimal(precision)
    variance = (actual - target).quantize(quantum, rounding=ROUND_HALF_UP)
    return Comparison(
        target=target,
        actual=actual,
        variance=variance,
        tolerance=tolerance,
        outside_tolerance=abs(variance) > tolerance,
    )


@dataclass(frozen=True)
class PlannedActual:
    planned: Decimal | None
    actual: Decimal | None
    delta: Decimal | None
    unit: str | None
    tolerance: Decimal | None
    status: str


def planned_versus_actual(
    planned: Decimal | None,
    actual: Decimal | None,
    tolerance: Decimal | None = None,
    unit: str | None = None,
    precision: str = "0.001",
    *,
    waived: bool = False,
    not_applicable: bool = False,
    not_recorded: bool = False,
) -> PlannedActual:
    if waived:
        return PlannedActual(planned, actual, None, unit, tolerance, "WAIVED")
    if not_applicable:
        return PlannedActual(planned, actual, None, unit, tolerance, "NOT_APPLICABLE")
    if planned is None:
        return PlannedActual(None, actual, None, unit, tolerance, "NO_TARGET")
    if not_recorded or actual is None:
        return PlannedActual(planned, None, None, unit, tolerance, "NOT_RECORDED")
    if tolerance is None:
        return PlannedActual(planned, actual, None, unit, None, "NO_TARGET")
    comparison = compare_measurement(planned, actual, tolerance, precision)
    status = "OUTSIDE_TOLERANCE" if comparison.outside_tolerance else "WITHIN_TOLERANCE"
    return PlannedActual(planned, actual, comparison.variance, unit, tolerance, status)
