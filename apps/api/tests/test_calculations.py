from decimal import Decimal

import pytest
from calculations import compare_measurement


def test_variance_is_deterministic_and_tolerance_is_inclusive():
    result = compare_measurement(Decimal("5.300"), Decimal("5.350"), Decimal("0.050"))
    assert result.variance == Decimal("0.050")
    assert result.outside_tolerance is False


def test_variance_outside_tolerance():
    result = compare_measurement(Decimal("1.050"), Decimal("1.046"), Decimal("0.003"))
    assert result.variance == Decimal("-0.004")
    assert result.outside_tolerance is True


def test_negative_tolerance_is_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        compare_measurement(Decimal("1"), Decimal("1"), Decimal("-0.1"))
