# Increment 5 — Calculation Engine

**Status:** Implemented (pending PO review / commit)

## Delivered

- ADR-003: approved v1 formula methodologies with §§A–J exact equations/constants/references
- Deterministic calculation package under `backend/app/calculations/`
- Formula registry with id@version identity
- Contracts: OK / MISSING / INVALID; ESTIMATED vs CALCULATED; explanation + provenance
- Recipe calculate API: `POST /api/v1/recipe-versions/{id}/calculate`
- Preview + scale endpoints
- Golden reference unit tests (including `source_reference` provenance alignment)
- Recipe editor **Calculate** panel with explanations

## Formulas (v1)

OG_ESTIMATE, FG_ESTIMATE, ABV, APPARENT_ATTENUATION, IBU (Tinseth), COLOR (Morey),
WATER_REQUIREMENTS, STRIKE_TEMP, RECIPE_SCALING, UNIT_CONVERSION

Each module `source_reference` cites the matching ADR-003 section (equation + constants).

## Explicitly deferred

Readiness engine (Increment 6); alternate IBU models; water laboratory chemistry.
