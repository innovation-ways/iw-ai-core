"""CR-00022 AC4: oss_check_catalog loader tests."""

from __future__ import annotations

import pytest


class TestCatalogLoader:
    """Tests for CatalogLoader scenarios."""

    def test_load_catalog_returns_dict(self) -> None:
        """Verifies that load catalog returns dict."""
        from dashboard.services.oss_check_catalog import load_catalog

        result = load_catalog()
        assert isinstance(result, dict)

    def test_load_catalog_returns_checkcopy_objects(self) -> None:
        """Verifies that load catalog returns checkcopy objects."""
        from dashboard.services.oss_check_catalog import CheckCopy, load_catalog

        result = load_catalog()
        assert all(isinstance(v, CheckCopy) for v in result.values())

    def test_load_catalog_keys_are_check_ids(self) -> None:
        """Verifies that load catalog keys are check ids."""
        from dashboard.services.oss_check_catalog import load_catalog

        result = load_catalog()
        for check_id in result:
            assert isinstance(check_id, str)
            assert len(check_id) > 0

    def test_get_copy_returns_checkcopy_or_none(self) -> None:
        """Verifies that get copy returns checkcopy or none."""
        from dashboard.services.oss_check_catalog import get_copy

        result = get_copy("OSS-CH-01")
        assert result is None or result.what_it_checks

    def test_get_copy_nonexistent_returns_none(self) -> None:
        """Verifies that get copy nonexistent returns none."""
        from dashboard.services.oss_check_catalog import get_copy

        result = get_copy("NONEXISTENT-CHECK-ID")
        assert result is None

    def test_production_cache_returns_same_object_identity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that production cache returns same object identity."""
        from dashboard.services import oss_check_catalog

        monkeypatch.setenv("IW_CORE_DEBUG", "false")

        oss_check_catalog._load_catalog_cached.cache_clear()

        result1 = oss_check_catalog.load_catalog()
        result2 = oss_check_catalog.load_catalog()

        assert result1 is result2

    def test_debug_mode_reloads_each_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that debug mode reloads each call."""
        from dashboard.services import oss_check_catalog

        monkeypatch.setenv("IW_CORE_DEBUG", "true")

        oss_check_catalog._load_catalog_cached.cache_clear()

        result1 = oss_check_catalog.load_catalog()
        result2 = oss_check_catalog.load_catalog()

        assert result1 is not result2

    def test_checkcopy_has_required_fields(self) -> None:
        """Verifies that checkcopy has required fields."""
        from dashboard.services.oss_check_catalog import get_copy

        entry = get_copy("OSS-CH-01")
        if entry is None:
            pytest.skip("OSS-CH-01 not in catalog")

        assert hasattr(entry, "what_it_checks")
        assert hasattr(entry, "how_it_tests")
        assert hasattr(entry, "risk_if_failing")
        assert hasattr(entry, "how_to_fix")
        assert hasattr(entry, "references")

        assert entry.what_it_checks.strip()
        assert entry.how_it_tests.strip()
        assert entry.risk_if_failing.strip()
        assert entry.how_to_fix.strip()
