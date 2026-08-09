# Increment 2 — Brewery & Equipment

**Status:** Implemented (pending PO review / commit)

## Delivered

- ADR-002 capturing orientation decisions authorized by PO
- NAS path defaults aligned to live `/volume1/docker/brewingos/...`
- Migration `002_brewery_equipment`: `breweries`, `equipment_profiles`, `audit_events`
- Brewery API: get primary / get by id / create / update
- Equipment API: list / create / get / update
- Audit events on brewery and equipment create/update
- Homebrewer-first UI: brewery setup → equipment setup with progressive disclosure
- Extract system type does not force mash capacity
- Validation + API unit tests

## Explicitly deferred

Ingredients, inventory, recipes, calculations, readiness (Increments 3–6).
Formula methodologies remain blocked pending a future ADR (ADR-002 §C).
