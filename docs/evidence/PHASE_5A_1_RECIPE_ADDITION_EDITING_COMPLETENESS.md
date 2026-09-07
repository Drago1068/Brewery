# Phase 5A-1 Evidence — Recipe Addition Editing Completeness

Work package: `BREWING_PHASE_5A_1_RECIPE_ADDITION_EDITING_COMPLETENESS`  
Status: implemented, pending targeted independent review. Not Phase 5A complete.

## Baseline

| Field | Value |
|---|---|
| Starting HEAD | `8c4c8c3581890dbc359bcccccaa7fe0cae414793` |
| Branch | `phase5a/recipe-editing-completeness` |
| Baseline tag | `v0.4.0-phase4` |
| Migration created | false (head remains `0015_phase4_journal_media_export`) |

## Behavior

Editing occurs on the in-memory Recipe Designer draft. Save still POSTs `/recipe-designs` and creates immutable `RecipeVersion` lineage. No persisted draft or publish semantics.

- Amount: positive decimal, max 4 fractional digits (`Numeric(14,4)`).
- Unit: only the ingredient `canonical_unit` (`g` \| `L` \| `each`); mismatched canonical units are rejected by existing `_ingredient_and_unit`.
- Stage: existing `RecipeIngredientInput` vocabulary.
- Timing: minutes, 0–10080; required for `BOIL`; omitted for non-timed stages (`FERMENTATION`, `PACKAGING`, `MISCELLANEOUS`, `FIRST_WORT`).
- Mash steps: `RecipeProcessStep` with `step_type=MASH`; add/edit/remove/order; sequences unique; boil step still appended from boil duration.

Deterministic calculation engine is unchanged. Hop amount/unit/stage/timing and fermentable amounts remain calculation inputs on save.
