from decimal import Decimal

import pytest

from app.domain.enums import InventoryTransactionType
from app.domain.inventory_math import (
    apply_transaction,
    available_quantity,
    on_hand_delta,
    reserved_delta,
)


def test_receipt_increases_on_hand():
    on_hand, reserved = apply_transaction(
        on_hand=Decimal("0"),
        reserved=Decimal("0"),
        transaction_type=InventoryTransactionType.RECEIPT,
        quantity=Decimal("10"),
    )
    assert on_hand == Decimal("10")
    assert reserved == Decimal("0")
    assert available_quantity(on_hand, reserved) == Decimal("10")


def test_consume_and_waste_reduce_on_hand():
    on_hand, reserved = apply_transaction(
        on_hand=Decimal("10"),
        reserved=Decimal("0"),
        transaction_type=InventoryTransactionType.CONSUMPTION,
        quantity=Decimal("3"),
    )
    assert on_hand == Decimal("7")

    on_hand, reserved = apply_transaction(
        on_hand=on_hand,
        reserved=reserved,
        transaction_type=InventoryTransactionType.WASTE,
        quantity=Decimal("1"),
    )
    assert on_hand == Decimal("6")


def test_adjustment_signed():
    assert on_hand_delta(InventoryTransactionType.ADJUSTMENT, Decimal("2")) == Decimal("2")
    assert on_hand_delta(InventoryTransactionType.ADJUSTMENT, Decimal("-1.5")) == Decimal("-1.5")


def test_reservation_foundation():
    on_hand, reserved = apply_transaction(
        on_hand=Decimal("10"),
        reserved=Decimal("0"),
        transaction_type=InventoryTransactionType.RESERVATION,
        quantity=Decimal("4"),
    )
    assert on_hand == Decimal("10")
    assert reserved == Decimal("4")
    assert available_quantity(on_hand, reserved) == Decimal("6")

    on_hand, reserved = apply_transaction(
        on_hand=on_hand,
        reserved=reserved,
        transaction_type=InventoryTransactionType.RESERVATION_RELEASE,
        quantity=Decimal("1"),
    )
    assert reserved == Decimal("3")
    assert available_quantity(on_hand, reserved) == Decimal("7")


def test_cannot_over_consume():
    with pytest.raises(ValueError, match="on-hand"):
        apply_transaction(
            on_hand=Decimal("2"),
            reserved=Decimal("0"),
            transaction_type=InventoryTransactionType.CONSUMPTION,
            quantity=Decimal("3"),
        )


def test_cannot_reserve_beyond_available():
    with pytest.raises(ValueError, match="available"):
        apply_transaction(
            on_hand=Decimal("5"),
            reserved=Decimal("3"),
            transaction_type=InventoryTransactionType.RESERVATION,
            quantity=Decimal("3"),
        )


def test_reserved_delta_helpers():
    assert reserved_delta(InventoryTransactionType.RECEIPT, Decimal("1")) == Decimal("0")
    assert reserved_delta(InventoryTransactionType.RESERVATION, Decimal("2")) == Decimal("2")
