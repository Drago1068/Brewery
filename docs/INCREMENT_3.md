# Increment 3 — Ingredients & Inventory

**Status:** Implemented (pending PO review / commit)

## Delivered

- Migration `003_ingredients_inventory`
  - `ingredients` + `fermentable_profiles` / `hop_profiles` / `yeast_profiles`
  - `ingredient_lots` with on-hand + reserved caches
  - append-only `inventory_transactions`
- Ingredient search/create/update API
- Inventory receive / adjust / use / discard / reserve / release-reservation
- Availability rollup with freshness labels (`OK|OPENED|EXPIRING|EXPIRED|UNKNOWN`)
- Pure ledger math module with unit tests (no silent negative balances)
- Lot-level `actual_alpha_acid` for hops (library default remains separate)
- Homebrewer inventory UI: table + Add / Adjust / Use / Discard
- Audit events for inventory movements

## Invariants enforced

- Inventory movement creates an `InventoryTransaction`
- History is append-oriented (no silent rewrites)
- Available = on_hand − reserved
- Receive unit must match ingredient `default_unit` (no silent conversion)
- Calculations do not mutate inventory (N/A this increment)

## Explicitly deferred

Recipes, calculations, readiness; purchasing; full unit-conversion matrix;
viability/propagation; warehouse WMS.
