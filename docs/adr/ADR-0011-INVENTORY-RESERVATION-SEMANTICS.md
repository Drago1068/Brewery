# ADR-0011 — Inventory Reservation Semantics

Status: Accepted for Phase 2

## Decision

Physical on-hand stock is derived only from append-only InventoryTransaction rows. `PURCHASE`, `RETURN`, and positive `ADJUSTMENT` add stock; `CONSUMPTION`, `WASTE`, and negative `ADJUSTMENT` remove stock; `TRANSFER` moves stock between locations with zero global delta.

Reservations are authoritative allocation records separate from physical stock. An active InventoryReservation reduces available stock but not on-hand stock. Creating/releasing a reservation also appends a zero-physical-delta `RESERVATION` or `RELEASE` transaction for a unified audit trail.

No mutable `quantity_on_hand` column exists. Corrections use new transactions; ledger rows are immutable. Negative on-hand or available balances are rejected by the application and PostgreSQL constraints protect transaction shape.

## Consequences

Balances are deterministic projections by ingredient, lot, and location. Availability is `on_hand - active_reserved`. Purchasing automation remains deferred; safety-stock and shortage results are warnings only.
