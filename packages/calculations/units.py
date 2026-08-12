from decimal import Decimal

GALLON_TO_LITER = Decimal("3.785411784")
POUND_TO_GRAM = Decimal("453.59237")
OUNCE_TO_GRAM = Decimal("28.349523125")


def gallons_to_liters(value: Decimal) -> Decimal:
    return value * GALLON_TO_LITER


def liters_to_gallons(value: Decimal) -> Decimal:
    return value / GALLON_TO_LITER


def pounds_to_kilograms(value: Decimal) -> Decimal:
    return value * POUND_TO_GRAM / Decimal("1000")


def kilograms_to_pounds(value: Decimal) -> Decimal:
    return value * Decimal("1000") / POUND_TO_GRAM


def ounces_to_grams(value: Decimal) -> Decimal:
    return value * OUNCE_TO_GRAM


def grams_to_ounces(value: Decimal) -> Decimal:
    return value / OUNCE_TO_GRAM


def fahrenheit_to_celsius(value: Decimal) -> Decimal:
    return (value - Decimal("32")) * Decimal("5") / Decimal("9")


def celsius_to_fahrenheit(value: Decimal) -> Decimal:
    return value * Decimal("9") / Decimal("5") + Decimal("32")
