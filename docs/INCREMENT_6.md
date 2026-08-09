# Increment 6 — Ready-to-Brew

**Status:** Implemented (pending PO review / commit)

## Delivered

- Pure readiness evaluator (`app/domain/readiness.py`) — no inventory/recipe mutation
- Checks: recipe completeness, equipment fit, inventory shortages, calculation state
- Overall: GREEN / YELLOW / RED with PASS / WARNING / BLOCKER distinctions
- API: `POST /api/v1/recipe-versions/{id}/readiness`
- Recipe UI: **Ready to brew?** panel with check list
- Unit + API tests

## Rules (v1)

| Area | Blocker examples | Warning examples |
|------|------------------|------------------|
| Completeness | missing batch size, fermentables, yeast, equipment | — |
| Equipment | kettle capacity &lt; batch size | mash capacity tight; unit mismatch |
| Inventory | — | shortage / missing stock |
| Calculations | OG/FG/ABV missing or invalid | water/strike incomplete |

## Explicitly deferred

BrewPlan creation / brew-day execution (Epic 2). Increment 7 hardening next.
