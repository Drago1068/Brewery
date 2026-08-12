# ADR-0010 — Recipe Calculation Snapshots

Status: Accepted for Phase 2

## Decision

Every Phase 2 RecipeVersion references its source EquipmentProfile and stores immutable JSON snapshots of:

- equipment assumptions used
- normalized calculation inputs
- authoritative calculation outputs
- formula/model identifiers
- unit and rounding policy version

Recipe ingredient/process rows are version-owned formulation data. A changed live equipment profile does not recalculate or rewrite historical recipe targets. Recalculation is an explicit clone-to-new-version operation.

## Compatibility

Phase 1A recipe versions remain valid. New snapshot fields are nullable for migration compatibility, while Phase 2 creation commands require complete snapshots.
