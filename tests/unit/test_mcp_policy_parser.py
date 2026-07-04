"""Unit tests for _parse_mcp_policy_block in orch.daemon.project_registry.

Covers: valid blocks kept, invalid values dropped, absent block returns None,
unknown keys produce a warning, tier key aliases accepted, empty block returns None.
"""

from __future__ import annotations

import logging

import pytest

from orch.daemon.project_registry import _parse_mcp_policy_block


class TestParseMcpPolicyBlock:
    """Covers _parse_mcp_policy_block parser behaviour."""

    def test_none_input_returns_none(self) -> None:
        """Absent block (None) returns None."""
        result = _parse_mcp_policy_block("proj", None)
        assert result is None

    def test_non_dict_input_returns_none(self, caplog: pytest.LogCaptureFixture) -> None:
        """Non-dict block returns None and logs a warning."""
        caplog.set_level(logging.WARNING)
        result = _parse_mcp_policy_block("proj", ["allow"])
        assert result is None
        assert caplog.text.lower().find("not a dict") != -1

    def test_valid_tool_name_entry_kept(self) -> None:
        """A valid tool name with a valid decision is kept as-is."""
        result = _parse_mcp_policy_block("proj", {"batch_cancel": "deny"})
        assert result is not None
        assert result.get("batch_cancel") == "deny"

    def test_valid_tier_key_kept(self) -> None:
        """Tier shorthand keys (tier1/tier2/tier3) with valid decisions are kept."""
        result = _parse_mcp_policy_block("proj", {"tier2": "ask", "tier3": "deny"})
        assert result is not None
        assert result.get("tier2") == "ask"
        assert result.get("tier3") == "deny"

    def test_default_key_kept(self) -> None:
        """The 'default' key with a valid decision is kept."""
        result = _parse_mcp_policy_block("proj", {"default": "allow"})
        assert result is not None
        assert result.get("default") == "allow"

    def test_invalid_decision_value_dropped_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Invalid decision strings are dropped and a warning is logged."""
        caplog.set_level(logging.WARNING)
        result = _parse_mcp_policy_block(
            "proj", {"batch_cancel": "permit", "approve_merge": "deny"}
        )
        # "permit" is invalid, "deny" is valid
        assert result is not None
        assert "batch_cancel" not in result
        assert result.get("approve_merge") == "deny"
        assert caplog.text.lower().find("invalid decision") != -1

    def test_all_invalid_entries_returns_none(self, caplog: pytest.LogCaptureFixture) -> None:
        """A block where every entry is invalid returns None."""
        caplog.set_level(logging.WARNING)
        result = _parse_mcp_policy_block("proj", {"batch_cancel": "WRONG", "tier2": 42})
        assert result is None

    def test_empty_dict_returns_none(self) -> None:
        """An empty dict returns None."""
        result = _parse_mcp_policy_block("proj", {})
        assert result is None

    def test_mixed_valid_invalid_keeps_only_valid(self) -> None:
        """Mixed block: valid entries kept, invalid ones dropped."""
        raw = {
            "tier1": "allow",
            "tier3": "BAD",
            "work_item_cancel": "ask",
            "batch_approve": "ALSO_BAD",
            "default": "deny",
        }
        result = _parse_mcp_policy_block("proj", raw)
        assert result is not None
        assert result.get("tier1") == "allow"
        assert result.get("work_item_cancel") == "ask"
        assert result.get("default") == "deny"
        assert "tier3" not in result
        assert "batch_approve" not in result

    def test_decision_value_case_normalised(self) -> None:
        """Decision values are normalised to lowercase."""
        result = _parse_mcp_policy_block("proj", {"tier2": "ALLOW"})
        assert result is not None
        assert result.get("tier2") == "allow"

    def test_unknown_key_kept_but_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """An unknown key (not a tool, tier key, or 'default') is kept but a warning is logged."""
        caplog.set_level(logging.WARNING)
        result = _parse_mcp_policy_block("proj", {"completely_unknown_tool": "allow"})
        assert result is not None
        assert result.get("completely_unknown_tool") == "allow"
        assert caplog.text.lower().find("no effect") != -1
