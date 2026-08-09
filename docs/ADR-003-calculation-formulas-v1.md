# ADR-003 — Epic 1 Calculation Formula Methodologies (v1)

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** ADR-002 deferred authoritative brewing formulas until Increment 5. Product Owner authorized proceeding with Increment 5, accepting the v1 set below.

## Decision

Authoritative Epic 1 calculations use the following **formula identities**. Changing behavior later requires a new formula version plus golden-fixture updates (handoff §34).

| Formula ID | Version | Method | Primary reference |
|------------|---------|--------|-------------------|
| `OG_ESTIMATE` | v1 | Brewhouse-efficiency points method (US weight/volume; metric converted first) | Standard homebrew gravity points method |
| `FG_ESTIMATE` | v1 | Apparent attenuation applied to estimated OG | `FG = 1 + (OG−1)×(1 − att/100)` |
| `ABV` | v1 | Simple ABV from OG/FG | `ABV% = (OG − FG) × 131.25` |
| `APPARENT_ATTENUATION` | v1 | From OG & FG | `((OG−FG)/(OG−1)) × 100` |
| `IBU` | v1 | Tinseth utilization (boil/whirlpool/first-wort; dry-hop = 0 IBU) | Glenn Tinseth |
| `COLOR` | v1 | Morey MCU → SRM | Dan Morey |
| `WATER_REQUIREMENTS` | v1 | Mash water + sparge (if provided) + boil-off + trub/fermenter losses when present; **no silent defaults** for missing losses | Equipment + mash step inputs |
| `STRIKE_TEMP` | v1 | Infusion strike-temperature ratio formula | Palmer / standard infusion equation |
| `RECIPE_SCALING` | v1 | Linear batch-size scale of mass/volume ingredient amounts | Proportional scaling |
| `UNIT_CONVERSION` | v1 | Fixed conversion factors (mass/volume/temp) | NIST / conventional brewing factors |

## Principles

1. Results are **ESTIMATED** / **CALCULATED**, never **MEASURED**.
2. Missing required inputs → status `MISSING` (no fabricated authoritative value).
3. Invalid inputs → status `INVALID`.
4. Formula id + version are returned with every authoritative result.
5. Historical stored explanations must retain formula identity; future formula changes do not rewrite history.

## Non-goals (v1)

- Rager / Garetz IBU models (may be added later as `IBU` v2+ alternatives)
- Advanced water chemistry / residual alkalinity laboratory
- Yeast viability / cell-count pitching rate
- AI-authored calculations

## Consequences

Increment 5 may implement the calculation engine and golden fixtures against this ADR.
