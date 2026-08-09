import pytest

from app.domain.enums import RecipeVersionStatus
from app.domain.recipe_rules import (
    RecipeVersionRuleError,
    assert_can_activate,
    assert_can_lock,
    assert_editable,
    is_immutable,
    next_version_number,
)


def test_draft_is_editable():
    assert_editable(RecipeVersionStatus.DRAFT)


@pytest.mark.parametrize(
    "status",
    [
        RecipeVersionStatus.ACTIVE,
        RecipeVersionStatus.SUPERSEDED,
        RecipeVersionStatus.LOCKED,
    ],
)
def test_non_draft_not_editable(status):
    with pytest.raises(RecipeVersionRuleError):
        assert_editable(status)
    assert is_immutable(status)


def test_version_numbers_increment():
    assert next_version_number([]) == 1
    assert next_version_number([1, 2, 4]) == 5


def test_locked_cannot_activate():
    with pytest.raises(RecipeVersionRuleError):
        assert_can_activate(RecipeVersionStatus.LOCKED)


def test_superseded_cannot_lock():
    with pytest.raises(RecipeVersionRuleError):
        assert_can_lock(RecipeVersionStatus.SUPERSEDED)


def test_active_can_lock():
    assert_can_lock(RecipeVersionStatus.ACTIVE)
