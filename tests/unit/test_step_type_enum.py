"""Unit tests for StepType enum values (no DB required)."""

from __future__ import annotations

import pytest

from orch.db.models import StepType


class TestStepTypeValues:
    """StepType enum must have self_assess as a first-class value."""

    def test_self_assess_value_exists(self) -> None:
        """self_assess must be a member of StepType."""
        assert hasattr(StepType, "self_assess")

    def test_self_assess_value_string(self) -> None:
        """self_assess.value must be the string 'self_assess'."""
        assert StepType.self_assess.value == "self_assess"

    def test_self_assess_is_enum_member(self) -> None:
        """self_assess must be a proper enum member (not an alias)."""
        assert StepType.self_assess is StepType["self_assess"]

    @pytest.mark.parametrize(
        "member",
        list(StepType),
        ids=[m.name for m in StepType],
    )
    def test_all_members_have_string_values(self, member: StepType) -> None:
        """Every StepType member must have a non-empty string value."""
        assert isinstance(member.value, str)
        assert member.value != ""
