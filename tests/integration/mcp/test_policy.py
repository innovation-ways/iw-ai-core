"""Integration tests for the MCP policy engine (orch/mcp/policy.py).

Covers all three precedence layers:
  1. DB McpPolicy row (highest priority)
  2. Project.config['mcp_policy'] dict (medium priority — exact-tool > tier > default)
  3. Built-in TIER_DEFAULTS (lowest priority)
Plus tie-break ordering between config keys.
"""

from __future__ import annotations

import pytest


class TestTierDefaults:
    """Covers built-in TIER_DEFAULTS when no DB row or config override exists."""

    def test_tier1_tool_defaults_to_allow(self, db_session, test_project):
        """Verifies that Tier-1 tools default to 'allow' when no policy overrides exist."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        decision = resolve_policy_decision(db_session, test_project.id, "work_item_next_id")
        assert decision == McpPolicyDecision.allow

    def test_tier2_tool_defaults_to_ask(self, db_session, test_project):
        """Verifies that Tier-2 tools default to 'ask' when no policy overrides exist."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        decision = resolve_policy_decision(db_session, test_project.id, "work_item_approve")
        assert decision == McpPolicyDecision.ask

    def test_tier3_tool_defaults_to_deny(self, db_session, test_project):
        """Verifies that Tier-3 tools default to 'deny' when no policy overrides exist."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        decision = resolve_policy_decision(db_session, test_project.id, "approve_merge")
        assert decision == McpPolicyDecision.deny

    def test_unknown_tool_defaults_to_ask(self, db_session, test_project):
        """Verifies that unknown tool names fall through to Tier-2 default (ask)."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        decision = resolve_policy_decision(db_session, test_project.id, "totally_unknown_tool")
        assert decision == McpPolicyDecision.ask

    def test_none_project_id_falls_through_to_tier_defaults(self, db_session):
        """Verifies that None project_id skips DB/config lookups and returns tier default."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        # Tier-3 tool with no project → deny by default
        decision = resolve_policy_decision(db_session, None, "batch_cancel")
        assert decision == McpPolicyDecision.deny


class TestDbPolicyRow:
    """Covers DB McpPolicy row override (highest priority)."""

    def test_db_row_overrides_tier_default(self, db_session, test_project):
        """Verifies that a McpPolicy row overrides the built-in tier default."""
        from orch.db.models import McpPolicy, McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        # Tier-2 default is 'ask', but we set a DB row to 'allow'
        row = McpPolicy(
            project_id=test_project.id,
            tool_name="work_item_approve",
            decision=McpPolicyDecision.allow,
            updated_by="test",
        )
        db_session.add(row)
        db_session.flush()

        decision = resolve_policy_decision(db_session, test_project.id, "work_item_approve")
        assert decision == McpPolicyDecision.allow

    def test_db_row_deny_overrides_allow_default(self, db_session, test_project):
        """Verifies that a DB deny row overrides a Tier-1 allow default."""
        from orch.db.models import McpPolicy, McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        row = McpPolicy(
            project_id=test_project.id,
            tool_name="work_item_next_id",
            decision=McpPolicyDecision.deny,
            updated_by="test",
        )
        db_session.add(row)
        db_session.flush()

        decision = resolve_policy_decision(db_session, test_project.id, "work_item_next_id")
        assert decision == McpPolicyDecision.deny

    def test_db_row_for_other_project_is_not_used(self, db_session, test_project):
        """Verifies that a DB row scoped to a different project_id is ignored."""
        from orch.db.models import McpPolicy, McpPolicyDecision, Project
        from orch.mcp.policy import resolve_policy_decision

        # Create a second project with its own policy row
        other = Project(
            id="other-project",
            display_name="Other",
            repo_root="/tmp/other",
            config={},
            enabled=True,
        )
        db_session.add(other)
        db_session.flush()

        row = McpPolicy(
            project_id="other-project",
            tool_name="work_item_approve",
            decision=McpPolicyDecision.allow,
            updated_by="test",
        )
        db_session.add(row)
        db_session.flush()

        # test_project should still see the tier default (ask)
        decision = resolve_policy_decision(db_session, test_project.id, "work_item_approve")
        assert decision == McpPolicyDecision.ask

    def test_db_row_takes_priority_over_config(self, db_session, test_project):
        """Verifies that DB row wins over Project.config['mcp_policy']."""
        from orch.db.models import McpPolicy, McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        # Set config to deny
        test_project.config = {"mcp_policy": {"work_item_approve": "deny"}}
        db_session.flush()

        # But DB row says allow
        row = McpPolicy(
            project_id=test_project.id,
            tool_name="work_item_approve",
            decision=McpPolicyDecision.allow,
            updated_by="test",
        )
        db_session.add(row)
        db_session.flush()

        decision = resolve_policy_decision(db_session, test_project.id, "work_item_approve")
        assert decision == McpPolicyDecision.allow


class TestProjectConfigPolicy:
    """Covers Project.config['mcp_policy'] dict (medium priority)."""

    def test_exact_tool_key_in_config(self, db_session, test_project):
        """Verifies that an exact tool name key in mcp_policy config overrides tier default."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        test_project.config = {"mcp_policy": {"batch_create": "allow"}}
        db_session.flush()

        decision = resolve_policy_decision(db_session, test_project.id, "batch_create")
        assert decision == McpPolicyDecision.allow

    def test_tier3_key_in_config_overrides_deny_default(self, db_session, test_project):
        """Verifies that tier3 key in config upgrades Tier-3 tools from deny to ask."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        test_project.config = {"mcp_policy": {"tier3": "ask"}}
        db_session.flush()

        decision = resolve_policy_decision(db_session, test_project.id, "approve_merge")
        assert decision == McpPolicyDecision.ask

    def test_tier2_key_in_config_overrides_ask_default(self, db_session, test_project):
        """Verifies that tier2 key in config changes Tier-2 tools from ask to allow."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        test_project.config = {"mcp_policy": {"tier2": "allow"}}
        db_session.flush()

        decision = resolve_policy_decision(db_session, test_project.id, "batch_approve")
        assert decision == McpPolicyDecision.allow

    def test_default_key_in_config_applies_to_all_tiers(self, db_session, test_project):
        """Verifies that 'default' key in config applies when no tier/exact-tool key matches."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        test_project.config = {"mcp_policy": {"default": "deny"}}
        db_session.flush()

        # Tier-1 normally allow, but config default overrides
        decision = resolve_policy_decision(db_session, test_project.id, "work_item_next_id")
        assert decision == McpPolicyDecision.deny

    def test_exact_tool_wins_over_tier_key(self, db_session, test_project):
        """Verifies exact-tool config key beats tier key for same tool."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        # tier2 says allow, but exact tool name says deny
        test_project.config = {"mcp_policy": {"tier2": "allow", "batch_create": "deny"}}
        db_session.flush()

        decision = resolve_policy_decision(db_session, test_project.id, "batch_create")
        assert decision == McpPolicyDecision.deny

    def test_exact_tool_wins_over_default_key(self, db_session, test_project):
        """Verifies exact-tool config key beats the default key."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        test_project.config = {"mcp_policy": {"default": "allow", "approve_merge": "deny"}}
        db_session.flush()

        decision = resolve_policy_decision(db_session, test_project.id, "approve_merge")
        assert decision == McpPolicyDecision.deny

    def test_tier_key_wins_over_default_key(self, db_session, test_project):
        """Verifies tier config key beats the default key."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        test_project.config = {"mcp_policy": {"default": "allow", "tier3": "ask"}}
        db_session.flush()

        decision = resolve_policy_decision(db_session, test_project.id, "batch_cancel")
        assert decision == McpPolicyDecision.ask

    def test_invalid_decision_string_in_config_is_ignored(self, db_session, test_project):
        """Verifies that unknown config decision strings fall through to next precedence layer."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        test_project.config = {"mcp_policy": {"batch_create": "banana"}}
        db_session.flush()

        # Falls through to tier default (ask for Tier-2)
        decision = resolve_policy_decision(db_session, test_project.id, "batch_create")
        assert decision == McpPolicyDecision.ask

    def test_no_mcp_policy_key_in_config_falls_through(self, db_session, test_project):
        """Verifies that config without mcp_policy key falls through to tier defaults."""
        from orch.db.models import McpPolicyDecision
        from orch.mcp.policy import resolve_policy_decision

        test_project.config = {"some_other_key": "value"}
        db_session.flush()

        decision = resolve_policy_decision(db_session, test_project.id, "approve_merge")
        assert decision == McpPolicyDecision.deny
