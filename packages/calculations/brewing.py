from dataclasses import dataclass
from decimal import Decimal

from .units import kilograms_to_pounds, liters_to_gallons

ZERO = Decimal("0")
ONE = Decimal("1")


def _positive(name: str, value: Decimal) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def gravity_points(specific_gravity: Decimal) -> Decimal:
    if specific_gravity < ONE:
        raise ValueError("Specific gravity cannot be below 1.000")
    return (specific_gravity - ONE) * Decimal("1000")


def fermentable_gravity_points(
    potential_ppg: Decimal,
    amount_grams: Decimal,
    volume_liters: Decimal,
    efficiency: Decimal,
) -> Decimal:
    _positive("amount_grams", amount_grams)
    _positive("volume_liters", volume_liters)
    if not ZERO < efficiency <= ONE:
        raise ValueError("Efficiency must be greater than 0 and at most 1")
    pounds = kilograms_to_pounds(amount_grams / Decimal("1000"))
    gallons = liters_to_gallons(volume_liters)
    return potential_ppg * pounds * efficiency / gallons


def expected_og(contributions: list[Decimal]) -> Decimal:
    if not contributions:
        raise ValueError("At least one fermentable contribution is required")
    return ONE + sum(contributions, ZERO) / Decimal("1000")


def apparent_attenuation(og: Decimal, fg: Decimal) -> Decimal:
    if og <= ONE or fg < ONE or fg > og:
        raise ValueError("Expected 1.000 <= FG <= OG and OG > 1.000")
    return (og - fg) / (og - ONE)


def expected_fg(og: Decimal, attenuation: Decimal) -> Decimal:
    if og <= ONE or not ZERO <= attenuation <= ONE:
        raise ValueError("OG must exceed 1.000 and attenuation must be between 0 and 1")
    return ONE + (og - ONE) * (ONE - attenuation)


def abv(og: Decimal, fg: Decimal) -> Decimal:
    if fg > og:
        raise ValueError("FG cannot exceed OG")
    return (og - fg) * Decimal("131.25")


def efficiency(extract_points_observed: Decimal, extract_points_potential: Decimal) -> Decimal:
    _positive("extract_points_potential", extract_points_potential)
    if extract_points_observed < 0:
        raise ValueError("Observed extract cannot be negative")
    return extract_points_observed / extract_points_potential


def tinseth_ibu(
    hop_grams: Decimal,
    alpha_acid_percent: Decimal,
    boil_minutes: Decimal,
    wort_gravity: Decimal,
    final_volume_liters: Decimal,
) -> Decimal:
    _positive("hop_grams", hop_grams)
    _positive("final_volume_liters", final_volume_liters)
    if not ZERO <= alpha_acid_percent <= Decimal("100"):
        raise ValueError("Alpha acid percent must be between 0 and 100")
    if boil_minutes < 0 or wort_gravity < ONE:
        raise ValueError("Boil time and wort gravity are outside the supported domain")
    bigness = Decimal("1.65") * (Decimal("0.000125") ** (wort_gravity - ONE))
    boil_factor = (ONE - (Decimal("-0.04") * boil_minutes).exp()) / Decimal("4.15")
    utilization = bigness * boil_factor
    return (
        hop_grams
        * Decimal("1000")
        * (alpha_acid_percent / Decimal("100"))
        * utilization
        / final_volume_liters
    )


def morey_srm(
    fermentables: list[tuple[Decimal, Decimal]], batch_volume_liters: Decimal
) -> Decimal:
    """Return Morey SRM from `(amount_grams, color_lovibond)` tuples."""
    _positive("batch_volume_liters", batch_volume_liters)
    if not fermentables:
        return ZERO
    gallons = liters_to_gallons(batch_volume_liters)
    mcu = sum(
        (kilograms_to_pounds(amount / Decimal("1000")) * lovibond / gallons)
        for amount, lovibond in fermentables
    )
    return Decimal("1.4922") * (mcu ** Decimal("0.6859"))


@dataclass(frozen=True)
class WaterVolumes:
    strike_liters: Decimal
    sparge_liters: Decimal
    total_liquor_liters: Decimal
    pre_boil_liters: Decimal
    post_boil_liters: Decimal


def brewing_water_volumes(
    grain_kg: Decimal,
    batch_liters: Decimal,
    mash_ratio_l_per_kg: Decimal,
    boil_minutes: Decimal,
    boil_off_l_per_hour: Decimal,
    grain_absorption_l_per_kg: Decimal,
    mash_tun_deadspace_liters: Decimal,
    kettle_loss_liters: Decimal,
    fermenter_loss_liters: Decimal,
    packaging_loss_liters: Decimal,
) -> WaterVolumes:
    for name, value in {
        "grain_kg": grain_kg,
        "batch_liters": batch_liters,
        "mash_ratio_l_per_kg": mash_ratio_l_per_kg,
    }.items():
        _positive(name, value)
    loss_inputs = [
        boil_minutes,
        boil_off_l_per_hour,
        grain_absorption_l_per_kg,
        mash_tun_deadspace_liters,
        kettle_loss_liters,
        fermenter_loss_liters,
        packaging_loss_liters,
    ]
    if any(value < 0 for value in loss_inputs):
        raise ValueError("Loss and duration inputs cannot be negative")
    post_boil = batch_liters + fermenter_loss_liters + packaging_loss_liters
    pre_boil = post_boil + boil_off_l_per_hour * boil_minutes / Decimal("60") + kettle_loss_liters
    strike = grain_kg * mash_ratio_l_per_kg + mash_tun_deadspace_liters
    total = pre_boil + grain_kg * grain_absorption_l_per_kg + mash_tun_deadspace_liters
    return WaterVolumes(strike, max(ZERO, total - strike), total, pre_boil, post_boil)


def strike_temperature_c(
    target_mash_c: Decimal, grain_temperature_c: Decimal, mash_ratio_l_per_kg: Decimal
) -> Decimal:
    _positive("mash_ratio_l_per_kg", mash_ratio_l_per_kg)
    quarts_per_pound = mash_ratio_l_per_kg * Decimal("0.479305709")
    return target_mash_c + Decimal("0.2") / quarts_per_pound * (
        target_mash_c - grain_temperature_c
    )


def specific_gravity_to_plato(sg: Decimal) -> Decimal:
    if sg < ONE:
        raise ValueError("Specific gravity cannot be below 1.000")
    return (
        Decimal("-616.868")
        + Decimal("1111.14") * sg
        - Decimal("630.272") * sg**2
        + Decimal("135.997") * sg**3
    )


def yeast_pitch_cells(
    volume_liters: Decimal, original_gravity: Decimal, rate_million_per_ml_plato: Decimal
) -> Decimal:
    _positive("volume_liters", volume_liters)
    _positive("rate_million_per_ml_plato", rate_million_per_ml_plato)
    plato = specific_gravity_to_plato(original_gravity)
    return volume_liters * Decimal("1000") * plato * rate_million_per_ml_plato * Decimal("1000000")


def residual_co2_volumes(beer_temperature_c: Decimal) -> Decimal:
    temperature_f = beer_temperature_c * Decimal("9") / Decimal("5") + Decimal("32")
    return (
        Decimal("3.0378")
        - Decimal("0.050062") * temperature_f
        + Decimal("0.00026555") * temperature_f**2
    )


def priming_sugar_grams(
    packaged_liters: Decimal, target_co2_volumes: Decimal, beer_temperature_c: Decimal
) -> Decimal:
    _positive("packaged_liters", packaged_liters)
    residual = residual_co2_volumes(beer_temperature_c)
    if target_co2_volumes <= residual:
        return ZERO
    return Decimal("4.0") * packaged_liters * (target_co2_volumes - residual)


def mineral_ppm(
    addition_grams: Decimal, ion_mass_fraction: Decimal, water_liters: Decimal
) -> Decimal:
    _positive("water_liters", water_liters)
    if addition_grams < 0 or not ZERO <= ion_mass_fraction <= ONE:
        raise ValueError("Mineral inputs are outside the supported domain")
    return addition_grams * Decimal("1000") * ion_mass_fraction / water_liters
