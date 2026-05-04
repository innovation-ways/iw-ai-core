"""Unit tests for _agent_subprocess_env() helper in orch.daemon.batch_manager.

The helper is the single chokepoint that prevents the daemon's allow-list
flags (IW_CORE_DAEMON_CONTEXT, IW_CORE_OPERATOR_APPLY) from leaking into
agent and QV-gate subprocesses. A regression here re-opens I-00041's bug.

These are all unit-scope: no DB, no testcontainers, pure env manipulation.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from orch.daemon.batch_manager import _agent_subprocess_env, _build_agent_env

if TYPE_CHECKING:
    import pytest


class TestAgentSubprocessEnvStrip:
    """R1.5 strip-helper tests — verifies allow-list flags are removed."""

    def test_strips_daemon_context_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IW_CORE_DAEMON_CONTEXT=true → stripped from child env."""
        monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
        env = _agent_subprocess_env()
        assert "IW_CORE_DAEMON_CONTEXT" not in env

    def test_strips_operator_apply_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IW_CORE_OPERATOR_APPLY=true → stripped from child env."""
        monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
        env = _agent_subprocess_env()
        assert "IW_CORE_OPERATOR_APPLY" not in env

    def test_strips_both_when_both_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Both allow-list flags set → both stripped."""
        monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
        env = _agent_subprocess_env()
        assert "IW_CORE_DAEMON_CONTEXT" not in env
        assert "IW_CORE_OPERATOR_APPLY" not in env


class TestAgentSubprocessEnvArm:
    """R1.5 arm-helper tests — verifies IW_CORE_AGENT_CONTEXT is always set."""

    def test_arms_agent_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IW_CORE_AGENT_CONTEXT=true is always set in child env."""
        monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
        env = _agent_subprocess_env()
        assert env.get("IW_CORE_AGENT_CONTEXT") == "true"

    def test_overrides_inherited_agent_context_with_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If IW_CORE_AGENT_CONTEXT is already set to false, helper enforces true."""
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "false")
        env = _agent_subprocess_env()
        assert env.get("IW_CORE_AGENT_CONTEXT") == "true"


class TestAgentSubprocessEnvExtra:
    """R1.5 extra-merge tests."""

    def test_extra_dict_is_merged_after_strip_and_arm(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """extra=dict is merged after strip+arm, preserving both."""
        monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
        extra = {"IW_CORE_PER_WORKTREE_DB": "true", "FOO": "bar"}
        env = _agent_subprocess_env(extra=extra)
        assert env.get("IW_CORE_PER_WORKTREE_DB") == "true"
        assert env.get("FOO") == "bar"
        assert "IW_CORE_DAEMON_CONTEXT" not in env

    def test_extra_can_override_agent_context_for_test_paths(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """extra={"IW_CORE_AGENT_CONTEXT": "false"} overrides the helper's arm.

        The helper's contract allows extras to override the arm (useful for
        test paths that need to prevent arming). This test documents that
        the contract permits override.
        """
        extra = {"IW_CORE_AGENT_CONTEXT": "false"}
        env = _agent_subprocess_env(extra=extra)
        assert env.get("IW_CORE_AGENT_CONTEXT") == "false"


class TestAgentSubprocessEnvIsolation:
    """R1.5 isolation tests — helper must not mutate real environment."""

    def test_does_not_mutate_real_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Calling the helper twice leaves os.environ unchanged; returned dicts are independent."""
        monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
        env1 = _agent_subprocess_env()
        env2 = _agent_subprocess_env()
        assert os.environ.get("IW_CORE_DAEMON_CONTEXT") == "true"
        assert "IW_CORE_DAEMON_CONTEXT" not in env1
        assert "IW_CORE_DAEMON_CONTEXT" not in env2
        env1["IW_CORE_FAKE_VAR"] = "from_env1"
        assert "IW_CORE_FAKE_VAR" not in env2

    def test_preserves_unrelated_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only allow-list flags are stripped; unrelated vars are preserved."""
        monkeypatch.setenv("PATH", "/usr/bin")
        monkeypatch.setenv("HOME", "/home/test")
        monkeypatch.setenv("IW_CORE_DB_HOST", "db.example.com")
        monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
        env = _agent_subprocess_env()
        assert env.get("PATH") == "/usr/bin"
        assert env.get("HOME") == "/home/test"
        # I-00062: IW_CORE_DB_* vars are stripped to prevent orch DB credential
        # leak. Use IW_CORE_ORCH_DB_* to access the operator's orch DB values.
        assert "IW_CORE_DB_HOST" not in env
        assert "IW_CORE_DAEMON_CONTEXT" not in env


class TestBuildAgentEnv:
    """R1.5 public delegator test — _build_agent_env must use the helper."""

    def test_build_agent_env_delegates_to_helper(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_build_agent_env with IW_CORE_DAEMON_CONTEXT set → env has no DAEMON_CONTEXT."""
        monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
        env = _build_agent_env(cli_tool="opencode", item_id="F-00042", worktree_path="/tmp/wt")
        assert "IW_CORE_DAEMON_CONTEXT" not in env
