# Units and Rounding

Canonical persistence/calculation units are grams, liters, degrees Celsius, specific gravity, SRM, ppm, and count (`each`). Gallons/liters, pounds/kilograms, ounces/grams, and Fahrenheit/Celsius convert only at boundaries.

Python `Decimal` is used throughout authoritative calculations. Intermediate results are not rounded. PostgreSQL numeric columns define persisted precision; calculation snapshots serialize full Decimal strings. UI display rounds only for readability (typically OG/FG 3 decimals, ABV/IBU/SRM/water 1 decimal) and never feeds displayed values back into calculations.

An ingredient has exactly one canonical inventory/recipe unit. Mixed-unit writes are rejected until an explicit boundary conversion is implemented, preventing accidental mass/volume/count mixing.
