# EPIC 1 IMPLEMENTATION REVIEW PACKAGE

**Product:** Brewing Intelligence & Competition OS  
**Epic:** 1 — Design the Beer  
**Handoff:** 1.2  
**Branch:** `main`  
**Date:** 2026-08-09  
**Status:** Implementation complete through Increment 7 — ready for independent review  

---

## 1. Executive implementation summary

Epic 1 delivers a homebrewer-first path from brewery/equipment setup through ingredient inventory, versioned recipe formulation, deterministic predictions with explanations, and Ready-to-Brew evaluation — stopping immediately before brew-day execution. Operational truth is PostgreSQL on NAS-backed Docker volumes; software truth is Git.

## 2. Final repository architecture

```text
BrewingOS/
  backend/          FastAPI + SQLAlchemy async + Alembic + calculations + pytest
  frontend/         React 19 + Vite + TypeScript + Vitest
  docs/             ADRs, increment notes, NAS/security/backup, this review package
  scripts/nas/      provision helper
  docker-compose.yml (+ .dev overlay)
  .github/workflows/ci.yml
```

Runtime: Compose project `brewingos` — `postgres`, `backend`, `frontend`, optional `backup`.

## 3. Files/modules added

Primary additions across Increments 1–7:

- `backend/app/api/v1/*` — brewery, equipment, ingredients, inventory, recipes, calculations, readiness, meta
- `backend/app/db/models.py` — domain tables
- `backend/app/domain/*` — enums, inventory math, recipe rules, readiness
- `backend/app/calculations/*` — formula modules + registry + recipe orchestrator
- `backend/app/services/*` — application services + audit
- `backend/alembic/versions/001`–`004`
- `frontend/src/App.tsx`, `RecipesPanel.tsx`, styles
- `docs/ADR-001`–`003`, `INCREMENT_1`–`7`, NAS/security/backup docs

## 4. Files/modules modified

- `.env.example`, `.gitignore`, `README.md`
- `docker-compose.yml`, `backend/requirements.txt`, `backend/scripts/entrypoint.sh`
- Scaffold health/config/session foundations from greenfield commit

## 5. Database schema changes

Tables: `app_meta`, `breweries`, `equipment_profiles`, `audit_events`, `ingredients`, `fermentable_profiles`, `hop_profiles`, `yeast_profiles`, `ingredient_lots`, `inventory_transactions`, `recipes`, `recipe_versions`, `recipe_intents`, `recipe_version_fermentables|hops|yeasts|adjuncts|water_additions|mash_steps|targets`.

## 6. Migration list

| Rev | Name |
|-----|------|
| 001 | `001_initial_foundation` |
| 002 | `002_brewery_equipment` |
| 003 | `003_ingredients_inventory` |
| 004 | `004_recipes` |

All additive; downgrades provided.

## 7. Domain entities implemented

Brewery, EquipmentProfile, Ingredient (+ fermentable/hop/yeast profiles), IngredientLot, InventoryTransaction, Recipe, RecipeVersion, RecipeIntent, recipe component lines, AuditEvent, AppMeta.

## 8. Domain invariants implemented

- RecipeVersion belongs to one Recipe; version numbers unique per recipe
- RecipeIntent is version-scoped
- Inventory movements append InventoryTransaction; history not rewritten
- Available = on_hand − reserved
- Calculations/readiness do not mutate inventory or recipes
- Estimated ≠ measured; missing inputs → MISSING (no fabrication)
- Draft-only in-place edits; ACTIVE/SUPERSEDED/LOCKED immutable via edit path
- Calc-critical ingredient attributes snapshotted on recipe lines
- AI is not the calculation authority
- Persistent data on bind mounts, not ephemeral container FS

## 9. API/service contracts

| Area | Endpoints (representative) |
|------|----------------------------|
| Meta/Health | `GET /health`, `/health/ready`, `/api/v1/meta` |
| Brewery | `GET/POST /api/v1/brewery`, `PATCH /api/v1/brewery/{id}` |
| Equipment | `/api/v1/breweries/{id}/equipment`, `/api/v1/equipment/{id}` |
| Ingredients | search/create/update under brewery + `/ingredients/{id}` |
| Inventory | receive/adjust/use/discard/reserve/release + availability |
| Recipes | CRUD-ish, versions, activate, lock, clone |
| Calculations | calculate version, preview, scale, formula catalog |
| Readiness | `POST /api/v1/recipe-versions/{id}/readiness` |

## 10. RecipeVersion behavior

Statuses: DRAFT → editable; activate supersedes prior ACTIVE; lock freezes; formulation changes to non-draft create a new version. Parent version linkage recorded.

## 11. RecipeIntent behavior

Optional sensory/formulation intent fields stored per RecipeVersion; new versions can change intent without rewriting prior intent rows.

## 12. Inventory transaction behavior

Types: RECEIPT, CONSUMPTION, ADJUSTMENT (signed), WASTE, RESERVATION, RESERVATION_RELEASE. Lot caches updated; ledger authoritative. Unit must match lot/ingredient default on receive (no silent conversion).

## 13. Calculation formulas/models

See ADR-003: OG points, FG from attenuation, ABV linear, apparent attenuation, Tinseth IBU, Morey SRM, water totals, strike temp, scaling, unit conversion.

## 14. Formula sources/references

Documented per result `source_reference` and in `docs/ADR-003-calculation-formulas-v1.md`.

## 15. Formula versions

All authoritative formulas shipped as `@v1` keys in the registry.

## 16. Calculation assumptions

Returned on each `CalculationResult` (efficiency meaning, Tinseth volume proxy, Morey °L, no silent boil-off defaults, etc.).

## 17. Golden reference fixtures

`backend/tests/test_calculations_golden.py` — OG/FG/ABV/IBU/color/water/strike/scaling/conversions + missing/invalid cases.

## 18. Calculation explanation/provenance behavior

Every result includes formula_id, version, status, kind, inputs, assumptions, missing/invalid lists, human explanation.

## 19. Readiness rules

Completeness blockers (batch, fermentables, yeast, equipment); kettle undersize blocker; inventory shortages warnings; OG/FG/ABV missing/invalid blockers; water/strike soft warnings. Overall GREEN/YELLOW/RED.

## 20. Unit tests

Inventory math, recipe rules, brewery/equipment validation, calculation golden fixtures, readiness evaluator, storage health.

## 21. Integration tests

`test_integration_journey.py` — inventory ledger → calculate → readiness domain journey; invalid calc non-fabrication.

## 22. E2E test

Automated domain/API journey covered. Full browser Playwright E2E deferred (documented). Primary UI journey manually exercisable: brewery → equipment → inventory → recipe → calculate → readiness.

## 23. Test results

Latest Increment 7 run: **61 passed** backend pytest; frontend `tsc` exit 0; `docker compose config` OK. Re-run before acceptance:

```bash
cd backend && pytest -q
cd frontend && npm test && npx tsc -b
docker compose config
```

## 24. Persistence/restart results

Increment 1 documented backend recreate retaining `app_meta`. Procedure for NAS recreate + representative data verification in `docs/BACKUP_RESTORE.md` and `docs/NAS_PERSISTENCE.md`. Live path: `/volume1/docker/brewingos/...` (ADR-002).

## 25. Docker/Compose configuration

`docker-compose.yml`: postgres 16, backend, frontend, backup profile; networks edge/app/data; ports 18181/18182 loopback by default.

## 26. NAS persistence configuration

Env-driven bind mounts; USB git root is not runtime DB storage; sibling workload paths forbidden.

## 27. Environment/secrets configuration

`.env.example` documents variables; real `.env` gitignored; NAS secrets file mode 600 recommended.

## 28. Backup/restore approach

`pg_dump -Fc` via backup sidecar; restore-into-isolated-env + verification checklist documented.

## 29. Security implementation

ADR-001 private access; no public Postgres; server-side validation; secrets out of git; Epic 1 auth = default actor + network isolation. Details: `docs/SECURITY_EPIC1.md`.

## 30. Audit implementation

Append-oriented `audit_events` for brewery/equipment changes, inventory movements, recipe create/version/activate/lock/clone.

## 31. Known limitations

- No login/multi-user IAM
- Vite dev frontend image in Compose
- Inventory unit conversion not automatic across mismatched units
- Browser E2E not automated
- Strike temp requires grain temp + mash water (often WARNING)
- Boil-off volume derived only when equipment rate + boil time present

## 32. Deferred functionality

Epic 2–5 domains (brew session, fermentation, packaging, sensory). Purchasing/WMS/CIP/commercial. Redis. Alternate IBU models. Water laboratory. AI recipe mutation.

## 33. Technical debt introduced

- Monolithic `App.tsx` + growing `RecipesPanel.tsx` (candidate split)
- Frontend not production-hardened image
- Availability list omits zero-stock library-only ingredients (name match gaps)
- Increment 6/7 changes may still be uncommitted relative to `30fa30f` at package authoring time — verify `git status` before review sign-off

## 34. Architecture deviations

- Live NAS path `/volume1/docker/brewingos` vs aspirational `/volume1/Apps` (ADR-002 accepted)
- Auth “per existing architecture” interpreted as network isolation + default actor (ADR-002)

## 35. Assumptions

- Single homebrewer brewery per deployment for Epic 1
- US gallon conversions for calc internals when needed
- Tinseth + Morey acceptable as v1 (ADR-003 PO-authorized via proceed)

## 36. Deployment implications

Deploy via NAS Compose with secrets env file; do not mount CODEX/AEGIS/claude paths; do not overwrite POS Tailscale Serve; migrate with `alembic upgrade head` on backend start.

## 37. Git branch

`main` (tracks `origin/main` when remote configured)

## 38. Relevant commits

| Commit | Summary |
|--------|---------|
| `3ccbe70` | Greenfield scaffold |
| `30fa30f` | Increments 1–5 implementation |
| _(pending)_ | Increments 6–7 readiness + hardening + this package — commit if not yet on remote |

## 39. Diff summary

Epic 1 adds full backend domain/API/calc/readiness stack, React UI flows, Alembic 001–004, ADRs, CI, and NAS/Docker ops docs. No Epic 2 brew-day execution included.

## 40. Items requiring independent review

1. ADR-003 formula choices (Tinseth, Morey, simple ABV)
2. Readiness severity policy (inventory shortage = WARNING not BLOCKER)
3. Auth deferral acceptability for private NAS
4. Snapshot strategy sufficiency for historical recipe integrity
5. Frontend Vite-dev image acceptability until production packaging
6. Confirm migrations applied on live NAS and persistence recreate test with representative recipe/inventory rows
7. Backup restore drill evidence (isolated environment)

---

**READY FOR INDEPENDENT ARCHITECTURE REVIEW**
