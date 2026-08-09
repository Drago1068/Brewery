"""Formula registry — identity and provenance for authoritative calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.calculations import (
    alcohol,
    attenuation,
    bitterness,
    color,
    conversions,
    gravity,
    mash,
    scaling,
    water,
)


@dataclass(frozen=True)
class FormulaSpec:
    formula_id: str
    version: str
    description: str
    source_reference: str
    compute: Callable[..., object]

    @property
    def key(self) -> str:
        return f"{self.formula_id}@{self.version}"


REGISTRY: dict[str, FormulaSpec] = {}


def _register(spec: FormulaSpec) -> None:
    REGISTRY[spec.key] = spec


def _bootstrap() -> None:
    if REGISTRY:
        return
    specs = [
        FormulaSpec(
            gravity.FORMULA_ID,
            gravity.FORMULA_VERSION,
            "Estimated original gravity via points method",
            gravity.SOURCE,
            gravity.estimate_og,
        ),
        FormulaSpec(
            attenuation.FG_ID,
            attenuation.FG_VERSION,
            "Estimated final gravity from attenuation",
            attenuation.FG_SOURCE,
            attenuation.estimate_fg,
        ),
        FormulaSpec(
            attenuation.ATT_ID,
            attenuation.ATT_VERSION,
            "Apparent attenuation from OG/FG",
            attenuation.ATT_SOURCE,
            attenuation.apparent_attenuation,
        ),
        FormulaSpec(
            alcohol.FORMULA_ID,
            alcohol.FORMULA_VERSION,
            "ABV from OG/FG",
            alcohol.SOURCE,
            alcohol.calculate_abv,
        ),
        FormulaSpec(
            bitterness.FORMULA_ID,
            bitterness.FORMULA_VERSION,
            "IBU via Tinseth",
            bitterness.SOURCE,
            bitterness.estimate_ibu,
        ),
        FormulaSpec(
            color.FORMULA_ID,
            color.FORMULA_VERSION,
            "Color SRM via Morey",
            color.SOURCE,
            color.estimate_srm,
        ),
        FormulaSpec(
            water.FORMULA_ID,
            water.FORMULA_VERSION,
            "Water requirements",
            water.SOURCE,
            water.water_requirements,
        ),
        FormulaSpec(
            mash.FORMULA_ID,
            mash.FORMULA_VERSION,
            "Strike temperature",
            mash.SOURCE,
            mash.strike_temperature,
        ),
        FormulaSpec(
            scaling.FORMULA_ID,
            scaling.FORMULA_VERSION,
            "Recipe batch scaling",
            scaling.SOURCE,
            scaling.scale_recipe,
        ),
        FormulaSpec(
            conversions.FORMULA_ID,
            conversions.FORMULA_VERSION,
            "Unit conversion",
            conversions.SOURCE,
            conversions.convert,
        ),
    ]
    for spec in specs:
        _register(spec)


def get_formula(formula_id: str, version: str) -> FormulaSpec:
    _bootstrap()
    key = f"{formula_id}@{version}"
    if key not in REGISTRY:
        raise KeyError(f"Unknown formula {key}")
    return REGISTRY[key]


def list_formulas() -> list[dict]:
    _bootstrap()
    return [
        {
            "formula_id": s.formula_id,
            "version": s.version,
            "key": s.key,
            "description": s.description,
            "source_reference": s.source_reference,
        }
        for s in sorted(REGISTRY.values(), key=lambda x: x.key)
    ]
