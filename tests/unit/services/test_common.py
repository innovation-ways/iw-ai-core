"""Unit tests for orch.services._common — ServiceError and pure helpers."""

from __future__ import annotations

import pytest


class TestServiceError:
    """Covers ServiceError construction and attribute access."""

    def test_service_error_stores_code_and_message(self):
        """Verifies that ServiceError exposes .code and .message attributes."""
        from orch.services._common import ServiceError

        err = ServiceError("something broke", code=4)
        assert err.code == 4
        assert err.message.find("something broke") != -1

    def test_service_error_is_exception(self):
        """Verifies that ServiceError is raisable and catchable as Exception."""
        from orch.services._common import ServiceError

        with pytest.raises(ServiceError) as exc_info:
            raise ServiceError("boom", code=1)
        assert exc_info.value.code == 1

    def test_service_error_default_code(self):
        """Verifies ServiceError defaults to code=1 when not specified."""
        from orch.services._common import ServiceError

        err = ServiceError("oops")
        assert err.code == 1


class TestListWorkItemsCursorClamping:
    """Covers the pure limit-clamping logic for list_work_items."""

    def test_clamp_limit_above_50(self):
        """Verifies that limit > 50 is clamped to 50."""
        from orch.services._common import clamp_limit

        assert clamp_limit(100) == 50

    def test_clamp_limit_at_50(self):
        """Verifies that limit == 50 is unchanged."""
        from orch.services._common import clamp_limit

        assert clamp_limit(50) == 50

    def test_clamp_limit_below_50(self):
        """Verifies that limit < 50 is unchanged."""
        from orch.services._common import clamp_limit

        assert clamp_limit(20) == 20

    def test_clamp_limit_zero(self):
        """Verifies that limit 0 is unchanged (no clamping below zero)."""
        from orch.services._common import clamp_limit

        assert clamp_limit(0) == 0
