"""Calculation result contracts — deterministic, explainable, no hidden fallbacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Optional


class ValueKind(StrEnum):
    """Cross-platform data principle labels."""

    TARGET = "TARGET"
    PLANNED = "PLANNED"
    CALCULATED = "CALCULATED"
    ESTIMATED = "ESTIMATED"
    MEASURED = "MEASURED"
    INHERITED = "INHERITED"
    MISSING = "MISSING"


class CalculationStatus(StrEnum):
    OK = "OK"
    MISSING = "MISSING"
    INVALID = "INVALID"


@dataclass(frozen=True)
class CalculationResult:
    formula_id: str
    formula_version: str
    status: CalculationStatus
    kind: ValueKind
    value: Optional[Decimal]
    unit: Optional[str]
    precision: int
    inputs: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    invalid_reasons: list[str] = field(default_factory=list)
    explanation: str = ""
    source_reference: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "formula_id": self.formula_id,
            "formula_version": self.formula_version,
            "formula_key": f"{self.formula_id}@{self.formula_version}",
            "status": self.status.value,
            "kind": self.kind.value,
            "value": str(self.value) if self.value is not None else None,
            "unit": self.unit,
            "precision": self.precision,
            "inputs": self.inputs,
            "assumptions": self.assumptions,
            "missing_inputs": self.missing_inputs,
            "invalid_reasons": self.invalid_reasons,
            "explanation": self.explanation,
            "source_reference": self.source_reference,
        }


def round_decimal(value: Decimal, places: int) -> Decimal:
    quant = Decimal("1").scaleb(-places)
    return value.quantize(quant)


def missing_result(
    *,
    formula_id: str,
    formula_version: str,
    unit: Optional[str],
    missing_inputs: list[str],
    precision: int,
    source_reference: str,
    inputs: Optional[dict[str, Any]] = None,
) -> CalculationResult:
    return CalculationResult(
        formula_id=formula_id,
        formula_version=formula_version,
        status=CalculationStatus.MISSING,
        kind=ValueKind.MISSING,
        value=None,
        unit=unit,
        precision=precision,
        inputs=inputs or {},
        missing_inputs=missing_inputs,
        explanation=(
            "Required inputs are missing. No authoritative value was fabricated. "
            f"Missing: {', '.join(missing_inputs)}."
        ),
        source_reference=source_reference,
    )


def invalid_result(
    *,
    formula_id: str,
    formula_version: str,
    unit: Optional[str],
    reasons: list[str],
    precision: int,
    source_reference: str,
    inputs: Optional[dict[str, Any]] = None,
) -> CalculationResult:
    return CalculationResult(
        formula_id=formula_id,
        formula_version=formula_version,
        status=CalculationStatus.INVALID,
        kind=ValueKind.MISSING,
        value=None,
        unit=unit,
        precision=precision,
        inputs=inputs or {},
        invalid_reasons=reasons,
        explanation="Inputs are invalid. " + "; ".join(reasons),
        source_reference=source_reference,
    )
