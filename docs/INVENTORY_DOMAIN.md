# Inventory Domain

Physical inventory is an append-only projection of `InventoryTransaction`; no authoritative `quantity_on_hand` column exists.

| Transaction | Physical projection |
|---|---:|
| PURCHASE, RETURN | `+quantity` |
| CONSUMPTION, WASTE | `-quantity` |
| ADJUSTMENT | signed quantity |
| TRANSFER | source `-quantity`, destination `+quantity`, global zero |
| RESERVATION, RELEASE | zero |

Reservations are separate active allocations. Creating/releasing one also appends a zero-physical-delta audit transaction. Balances are available globally and can be filtered by ingredient, lot, or location. Writes reject canonical-unit mismatches, invalid relationships, cross-owner identifiers, and debits/reservations that exceed availability.

`SafetyStockPolicy` compares available stock with an enabled threshold and returns `OK`, `BELOW_SAFETY_STOCK`, or `SHORTAGE`. Purchasing automation is not part of Phase 2.
