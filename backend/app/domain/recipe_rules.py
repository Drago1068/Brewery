"""Pure RecipeVersion state-transition rules."""

from __future__ import annotations

from app.domain.enums import (
    EDITABLE_VERSION_STATUSES,
    IMMUTABLE_VERSION_STATUSES,
    RecipeVersionStatus,
)


class RecipeVersionRuleError(ValueError):
    pass


def assert_editable(status: RecipeVersionStatus | str) -> None:
    value = RecipeVersionStatus(status)
    if value not in EDITABLE_VERSION_STATUSES:
        raise RecipeVersionRuleError(
            f"RecipeVersion status {value.value} is not editable; create a new version instead"
        )


def assert_can_activate(status: RecipeVersionStatus | str) -> None:
    value = RecipeVersionStatus(status)
    if value == RecipeVersionStatus.LOCKED:
        raise RecipeVersionRuleError("LOCKED RecipeVersion cannot be activated")
    if value == RecipeVersionStatus.SUPERSEDED:
        raise RecipeVersionRuleError("SUPERSEDED RecipeVersion cannot be reactivated")


def assert_can_lock(status: RecipeVersionStatus | str) -> None:
    value = RecipeVersionStatus(status)
    if value == RecipeVersionStatus.LOCKED:
        raise RecipeVersionRuleError("RecipeVersion is already LOCKED")
    if value == RecipeVersionStatus.SUPERSEDED:
        raise RecipeVersionRuleError("SUPERSEDED RecipeVersion cannot be locked")


def next_version_number(existing_numbers: list[int]) -> int:
    if not existing_numbers:
        return 1
    return max(existing_numbers) + 1


def is_immutable(status: RecipeVersionStatus | str) -> bool:
    return RecipeVersionStatus(status) in IMMUTABLE_VERSION_STATUSES
