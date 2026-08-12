from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ScalingFactors:
    volume: Decimal
    fermentable: Decimal
    hop: Decimal
    yeast: Decimal
    salt: Decimal


def recipe_scaling_factors(
    source_batch_liters: Decimal,
    target_batch_liters: Decimal,
    source_efficiency: Decimal,
    target_efficiency: Decimal,
    source_total_liquor_liters: Decimal,
    target_total_liquor_liters: Decimal,
) -> ScalingFactors:
    for name, value in {
        "source_batch_liters": source_batch_liters,
        "target_batch_liters": target_batch_liters,
        "source_efficiency": source_efficiency,
        "target_efficiency": target_efficiency,
        "source_total_liquor_liters": source_total_liquor_liters,
        "target_total_liquor_liters": target_total_liquor_liters,
    }.items():
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero")
    volume = target_batch_liters / source_batch_liters
    return ScalingFactors(
        volume=volume,
        fermentable=volume * source_efficiency / target_efficiency,
        hop=volume,
        yeast=volume,
        salt=target_total_liquor_liters / source_total_liquor_liters,
    )


def scale_quantity(quantity: Decimal, factor: Decimal) -> Decimal:
    if quantity < 0 or factor <= 0:
        raise ValueError("Quantity cannot be negative and factor must be positive")
    return quantity * factor
