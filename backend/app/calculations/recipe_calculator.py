"""Orchestrate recipe-level calculations from a RecipeVersion-like payload."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.calculations.alcohol import calculate_abv
from app.calculations.attenuation import apparent_attenuation, estimate_fg
from app.calculations.bitterness import estimate_ibu
from app.calculations.color import estimate_srm
from app.calculations.gravity import estimate_og
from app.calculations.mash import strike_temperature
from app.calculations.types import CalculationResult
from app.calculations.water import pre_post_boil_volumes, water_requirements


def _dec(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(value))


def calculate_recipe(payload: dict[str, Any]) -> dict[str, Any]:
    """payload mirrors RecipeVersion fields + nested component lists."""
    fermentables = [
        {
            "amount": f.get("amount"),
            "unit": f.get("unit"),
            "potential_sg": f.get("potential_sg"),
            "color_lovibond": f.get("color_lovibond"),
            "ingredient_name": f.get("ingredient_name"),
        }
        for f in payload.get("fermentables") or []
    ]
    hops = [
        {
            "amount": h.get("amount"),
            "unit": h.get("unit"),
            "alpha_acid": h.get("alpha_acid"),
            "stage": h.get("stage"),
            "time_minutes": h.get("time_minutes"),
            "ingredient_name": h.get("ingredient_name"),
        }
        for h in payload.get("hops") or []
    ]
    yeasts = payload.get("yeasts") or []
    mash_steps = payload.get("mash_steps") or []

    batch_size = _dec(payload.get("batch_size"))
    batch_unit = payload.get("batch_size_unit")
    efficiency = _dec(payload.get("brewhouse_efficiency"))

    og = estimate_og(
        fermentables=fermentables,
        batch_size=batch_size,
        batch_size_unit=batch_unit,
        efficiency_percent=efficiency,
    )

    attenuation = None
    if yeasts:
        attenuation = _dec(yeasts[0].get("expected_attenuation"))

    fg = estimate_fg(og=og.value if og.status.value == "OK" else None, attenuation_percent=attenuation)
    abv = calculate_abv(
        og=og.value if og.status.value == "OK" else None,
        fg=fg.value if fg.status.value == "OK" else None,
    )
    att = apparent_attenuation(
        og=og.value if og.status.value == "OK" else None,
        fg=fg.value if fg.status.value == "OK" else None,
    )
    ibu = estimate_ibu(
        hops=hops,
        batch_size=batch_size,
        batch_size_unit=batch_unit,
        boil_gravity=og.value if og.status.value == "OK" else None,
    )
    srm = estimate_srm(
        fermentables=fermentables,
        batch_size=batch_size,
        batch_size_unit=batch_unit,
    )

    mash_water = sparge_water = mash_water_unit = sparge_water_unit = None
    mash_temp = None
    if mash_steps:
        step0 = mash_steps[0]
        mash_water = _dec(step0.get("mash_water_volume"))
        mash_water_unit = step0.get("mash_water_unit")
        sparge_water = _dec(step0.get("sparge_water_volume"))
        sparge_water_unit = step0.get("sparge_water_unit")
        mash_temp = _dec(step0.get("target_temperature_c"))

    water = water_requirements(
        mash_water=mash_water,
        mash_water_unit=mash_water_unit,
        sparge_water=sparge_water,
        sparge_water_unit=sparge_water_unit,
        boil_off=_dec(payload.get("boil_off")),
        boil_off_unit=payload.get("boil_off_unit"),
        trub_loss=_dec(payload.get("trub_loss")),
        trub_loss_unit=payload.get("trub_loss_unit"),
        output_unit=batch_unit or "gal",
    )
    volumes = pre_post_boil_volumes(
        batch_size=batch_size,
        batch_size_unit=batch_unit,
        boil_off=_dec(payload.get("boil_off")),
        boil_off_unit=payload.get("boil_off_unit"),
        trub_loss=_dec(payload.get("trub_loss")),
        trub_loss_unit=payload.get("trub_loss_unit"),
    )

    grain_weight = None
    grain_unit = None
    if fermentables:
        # Sum grain mass only when all share same unit; else leave missing for strike.
        units = {str(f.get("unit")) for f in fermentables if f.get("unit")}
        if len(units) == 1:
            grain_unit = next(iter(units))
            grain_weight = sum((Decimal(str(f["amount"])) for f in fermentables), Decimal("0"))

    grain_temp = _dec(payload.get("grain_temp_c"))
    strike = strike_temperature(
        mash_temp_c=mash_temp,
        grain_temp_c=grain_temp,
        mash_water=mash_water,
        mash_water_unit=mash_water_unit,
        grain_weight=grain_weight,
        grain_weight_unit=grain_unit,
    )

    results: dict[str, CalculationResult] = {
        "og": og,
        "fg": fg,
        "abv": abv,
        "apparent_attenuation": att,
        "ibu": ibu,
        "color_srm": srm,
        "water_total": water,
        "pre_boil_volume": volumes["pre_boil_volume"],
        "post_boil_volume": volumes["post_boil_volume"],
        "boil_off": volumes["boil_off"],
        "strike_temp": strike,
    }
    return {
        "kind_note": "All predictive values are ESTIMATED/CALCULATED — not MEASURED.",
        "results": {key: result.to_dict() for key, result in results.items()},
    }
