"""Inventory ledger math — pure, side-effect free."""

from __future__ import annotations

from decimal import Decimal

from app.domain.enums import InventoryTransactionType

# Transaction types that reduce on-hand (quantity must be > 0).
_DECREASE_ON_HAND = frozenset(
    {
        InventoryTransactionType.CONSUMPTION,
        InventoryTransactionType.WASTE,
    }
)

# Transaction types that increase on-hand (quantity must be > 0).
_INCREASE_ON_HAND = frozenset(
    {
        InventoryTransactionType.RECEIPT,
    }
)


def on_hand_delta(transaction_type: InventoryTransactionType, quantity: Decimal) -> Decimal:
    """Return signed on-hand change for a transaction.

    - RECEIPT: +quantity (quantity > 0)
    - CONSUMPTION / WASTE: -quantity (quantity > 0)
    - ADJUSTMENT: quantity is signed (+ increase / - decrease)
    - RESERVATION / RESERVATION_RELEASE: 0 on-hand change (affect reserved only)
    """
    if transaction_type in _INCREASE_ON_HAND:
        if quantity <= 0:
            raise ValueError("RECEIPT quantity must be greater than zero")
        return quantity
    if transaction_type in _DECREASE_ON_HAND:
        if quantity <= 0:
            raise ValueError(f"{transaction_type.value} quantity must be greater than zero")
        return -quantity
    if transaction_type == InventoryTransactionType.ADJUSTMENT:
        if quantity == 0:
            raise ValueError("ADJUSTMENT quantity must be non-zero")
        return quantity
    if transaction_type in {
        InventoryTransactionType.RESERVATION,
        InventoryTransactionType.RESERVATION_RELEASE,
    }:
        if quantity <= 0:
            raise ValueError(f"{transaction_type.value} quantity must be greater than zero")
        return Decimal("0")
    raise ValueError(f"Unsupported transaction type: {transaction_type}")


def reserved_delta(transaction_type: InventoryTransactionType, quantity: Decimal) -> Decimal:
    """Return signed reserved-quantity change."""
    if transaction_type == InventoryTransactionType.RESERVATION:
        if quantity <= 0:
            raise ValueError("RESERVATION quantity must be greater than zero")
        return quantity
    if transaction_type == InventoryTransactionType.RESERVATION_RELEASE:
        if quantity <= 0:
            raise ValueError("RESERVATION_RELEASE quantity must be greater than zero")
        return -quantity
    return Decimal("0")


def available_quantity(on_hand: Decimal, reserved: Decimal) -> Decimal:
    """Available = on_hand - reserved. Never silently invent stock."""
    return on_hand - reserved


def apply_transaction(
    *,
    on_hand: Decimal,
    reserved: Decimal,
    transaction_type: InventoryTransactionType,
    quantity: Decimal,
) -> tuple[Decimal, Decimal]:
    """Apply one transaction to lot balances. Raises if result would go negative."""
    new_on_hand = on_hand + on_hand_delta(transaction_type, quantity)
    new_reserved = reserved + reserved_delta(transaction_type, quantity)

    if new_on_hand < 0:
        raise ValueError("Transaction would make on-hand quantity negative")
    if new_reserved < 0:
        raise ValueError("Transaction would make reserved quantity negative")
    if available_quantity(new_on_hand, new_reserved) < 0:
        raise ValueError("Transaction would make available quantity negative")

    return new_on_hand, new_reserved
