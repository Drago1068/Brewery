# Increment 4 — Recipe & RecipeVersion

**Status:** Implemented (pending PO review / commit)

## Delivered

- Migration `004_recipes`
  - `recipes`, `recipe_versions` (unique version_number per recipe)
  - `recipe_intents` (version-scoped)
  - Normalized component tables with **calculation-critical snapshots**
  - mash steps + TARGET rows
- Domain rules: draft-only edit; activate supersedes prior ACTIVE; lock; clone
- APIs: create/list/get/update recipe; draft update; new version; activate; lock; clone
- Recipe editor UI (overview, intent, fermentables, hops, yeast, mash, version history)
- Unit tests for versioning rules + API smoke tests

## Invariants

1. Every RecipeVersion belongs to exactly one Recipe
2. Version numbers unique within a Recipe
3. RecipeIntent is version-aware
4. Ingredient-library edits cannot silently rewrite historical recipe meaning (snapshots)
5. Locked / active / superseded versions are not silently edited — create a new version

## Explicitly deferred

Calculations (Increment 5), readiness (Increment 6), BrewSession immutability trigger (Epic 2).
