"""Unit tests for _parse_overlap_gate in project_registry — CR-00058.

Tests the parsing and validation of the optional overlap_gate block
from .iw-orch.json. Verifies default synthesis, warning on malformed
input, and per-side independence.
"""

from __future__ import annotations

import pytest

from orch.daemon.project_registry import _parse_overlap_gate
from orch.daemon.scope_overlap import DEFAULT_ALLOW_PATTERNS, DEFAULT_BLOCK_PATTERNS


class TestParseOverlapGate:
    """Tests for _parse_overlap_gate function."""

    def test_parse_valid_overlap_gate(self) -> None:
        """Full block returned via ProjectConfig."""
        raw = {
            "block_on_overlap": ["src/**", "docs/**"],
            "allow_on_overlap": ["tests/**", "**/*.test.py"],
        }
        block, allow = _parse_overlap_gate("test-proj", raw)
        assert block == ["src/**", "docs/**"]
        assert allow == ["tests/**", "**/*.test.py"]

    def test_parse_missing_block_synthesises_default(self) -> None:
        """Absent key → default block=["**/*"], allow=test patterns."""
        block, allow = _parse_overlap_gate("test-proj", None)
        assert block == list(DEFAULT_BLOCK_PATTERNS)
        assert allow == list(DEFAULT_ALLOW_PATTERNS)

    def test_parse_malformed_block_warns_and_defaults(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Non-list values → warning + default for that side."""
        # block_on_overlap is a string instead of list
        raw = {
            "block_on_overlap": "not a list",
            "allow_on_overlap": ["tests/**"],
        }
        with caplog.at_level("WARNING", logger="orch.daemon.project_registry"):
            block, allow = _parse_overlap_gate("test-proj", raw)
        assert block == list(DEFAULT_BLOCK_PATTERNS), "block side should default"
        assert allow == ["tests/**"], "allow side should be preserved"
        assert any("not a list" in msg for msg in caplog.messages), (
            "Warning should mention the malformed value"
        )

    def test_parse_malformed_allow_warns_and_defaults(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """allow_on_overlap is not a list → warning + default for that side."""
        raw = {
            "block_on_overlap": ["src/**"],
            "allow_on_overlap": {"not": "a list"},
        }
        with caplog.at_level("WARNING", logger="orch.daemon.project_registry"):
            block, allow = _parse_overlap_gate("test-proj", raw)
        assert block == ["src/**"], "block side should be preserved"
        assert allow == list(DEFAULT_ALLOW_PATTERNS), "allow side should default"
        assert any("not a list" in msg for msg in caplog.messages), (
            "Warning should mention the malformed value"
        )

    def test_parse_non_dict_raw_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """raw is not a dict → warn and return full defaults."""
        raw = "not a dictionary"
        with caplog.at_level("WARNING", logger="orch.daemon.project_registry"):
            block, allow = _parse_overlap_gate("test-proj", raw)
        assert block == list(DEFAULT_BLOCK_PATTERNS)
        assert allow == list(DEFAULT_ALLOW_PATTERNS)
        assert any(
            "not a dict" in msg.lower() or "dictionary" in msg.lower() for msg in caplog.messages
        )

    def test_parse_non_string_pattern_dropped(self, caplog: pytest.LogCaptureFixture) -> None:
        """List with mixed types → drop non-strings, warn per entry."""
        raw = {
            "block_on_overlap": ["src/**", 123, "docs/**", None],
            "allow_on_overlap": ["tests/**", {"bad": "dict"}],
        }
        with caplog.at_level("WARNING", logger="orch.daemon.project_registry"):
            block, allow = _parse_overlap_gate("test-proj", raw)
        # Non-string entries (123, None) should be dropped
        assert block == ["src/**", "docs/**"], (
            f"Non-string block entries should be dropped. Got: {block}"
        )
        assert allow == ["tests/**"], f"Non-string allow entries should be dropped. Got: {allow}"
        # Should have warned about 3 bad entries (123, None, {"bad": "dict"})
        warnings = [rec.message for rec in caplog.records]
        assert len(warnings) >= 3, f"Expected >=3 warnings, got: {warnings}"

    def test_partial_block_uses_default_for_missing_side(self) -> None:
        """Supplying allow_on_overlap without block_on_overlap → block side defaults."""
        raw = {
            "allow_on_overlap": ["tests/**", "docs/**"],
            # no block_on_overlap
        }
        block, allow = _parse_overlap_gate("test-proj", raw)
        assert block == list(DEFAULT_BLOCK_PATTERNS), (
            "Missing block_on_overlap should default to ['**/*']"
        )
        assert allow == ["tests/**", "docs/**"]

    def test_partial_allow_uses_default_for_missing_side(self) -> None:
        """Supplying block_on_overlap without allow_on_overlap → allow side defaults."""
        raw = {
            "block_on_overlap": ["src/**"],
            # no allow_on_overlap
        }
        block, allow = _parse_overlap_gate("test-proj", raw)
        assert block == ["src/**"]
        assert allow == list(DEFAULT_ALLOW_PATTERNS), (
            "Missing allow_on_overlap should default to test patterns"
        )

    def test_empty_block_list_honored(self) -> None:
        """block_on_overlap=[] means 'never block' — honoured even though it's unusual."""
        raw = {
            "block_on_overlap": [],
            "allow_on_overlap": ["tests/**"],
        }
        block, allow = _parse_overlap_gate("test-proj", raw)
        assert block == [], f"Empty block list should be honoured. Got: {block}"
        assert allow == ["tests/**"]

    def test_empty_allow_list_honored(self) -> None:
        """allow_on_overlap=[] means 'no exemptions' — honoured."""
        raw = {
            "block_on_overlap": ["**/*"],
            "allow_on_overlap": [],
        }
        block, allow = _parse_overlap_gate("test-proj", raw)
        assert block == ["**/*"]
        assert allow == [], f"Empty allow list should be honoured. Got: {allow}"

    def test_both_empty_means_no_gating(self) -> None:
        """block_on_overlap=[] and allow_on_overlap=[] → gate completely off."""
        raw = {
            "block_on_overlap": [],
            "allow_on_overlap": [],
        }
        block, allow = _parse_overlap_gate("test-proj", raw)
        assert block == []
        assert allow == []
