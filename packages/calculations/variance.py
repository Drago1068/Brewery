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
