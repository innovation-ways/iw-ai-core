"""Unit tests for orch.agent_runtime.resolver — cascade resolution of (cli_tool, model).

These tests use unittest.mock to simulate SQLAlchemy session behavior,
allowing pure unit testing without a testcontainer.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeProjectConfig:
    """Minimal ProjectConfig for resolver tests."""

    def __init__(self, cli_tool: str | None = "opencode", model: str | None = "minimax") -> None:
        self.cli_tool = cli_tool
        self.model = model


class FakeWorkItem:
    def __init__(self, agent_runtime_option_id: int | None = None) -> None:
        self.agent_runtime_option_id = agent_runtime_option_id


class FakeWorkflowStep:
    def __init__(self, agent_runtime_option_id: int | None = None) -> None:
        self.agent_runtime_option_id = agent_runtime_option_id


def _make_option(
    option_id: int,
    cli_tool: str,
    model: str,
    enabled: bool = True,
    is_default: bool = False,
) -> MagicMock:
    """Create a mock AgentRuntimeOption with the given attributes."""
    opt = MagicMock()
    opt.id = option_id
    opt.cli_tool = cli_tool
    opt.model = model
    opt.cli_label = cli_tool.title()
    opt.model_label = model
    opt.display_name = f"{cli_tool} + {model}"
    opt.enabled = enabled
    opt.is_default = is_default
    opt.sort_order = option_id * 10
    return opt


# ---------------------------------------------------------------------------
# Tests — happy path cascade
# ---------------------------------------------------------------------------


def test_resolver_step_override_wins(caplog: pytest.LogCaptureFixture) -> None:
    """AC3: step-level override takes precedence over item-level."""
    from orch.agent_runtime.resolver import resolve_runtime

    opt1 = _make_option(option_id=1, cli_tool="opencode", model="minimax", is_default=True)
    opt5 = _make_option(option_id=5, cli_tool="claude", model="claude-opus-4-7")

    # Mock the helper functions to return specific options based on id
    with (
        patch("orch.agent_runtime.resolver._load_option") as mock_load,
        patch("orch.agent_runtime.resolver._load_default") as mock_load_default,
    ):

        def load_side_effect(session, opt_id):
            """Return load side effect."""
            return {1: opt1, 5: opt5}.get(opt_id)

        mock_load.side_effect = load_side_effect
        mock_load_default.return_value = opt1

        step = FakeWorkflowStep(agent_runtime_option_id=5)
        item = FakeWorkItem(agent_runtime_option_id=1)
        project = FakeProjectConfig()

        result = resolve_runtime(MagicMock(), step=step, item=item, project=project)

        assert result.id == 5
        assert result.cli_tool == "claude"
        assert result.model == "claude-opus-4-7"


def test_resolver_item_override_wins_when_no_step_override(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC2: item-level override is used when step has no override."""
    from orch.agent_runtime.resolver import resolve_runtime

    opt1 = _make_option(option_id=1, cli_tool="opencode", model="minimax", is_default=True)
    opt4 = _make_option(option_id=4, cli_tool="claude", model="claude-sonnet-4-6")

    with (
        patch("orch.agent_runtime.resolver._load_option") as mock_load,
        patch("orch.agent_runtime.resolver._load_default") as mock_load_default,
    ):

        def load_side_effect(session, opt_id):
            """Return load side effect."""
            return {1: opt1, 4: opt4}.get(opt_id)

        mock_load.side_effect = load_side_effect
        mock_load_default.return_value = opt1

        step = FakeWorkflowStep(agent_runtime_option_id=None)
        item = FakeWorkItem(agent_runtime_option_id=4)
        project = FakeProjectConfig()

        result = resolve_runtime(MagicMock(), step=step, item=item, project=project)

        assert result.id == 4
        assert result.cli_tool == "claude"
        assert result.model == "claude-sonnet-4-6"


def test_resolver_project_default_fallback(caplog: pytest.LogCaptureFixture) -> None:
    """AC1: project.toml (cli_tool, model) pair is used when no item/step override."""
    from orch.agent_runtime.resolver import resolve_runtime

    opt1 = _make_option(option_id=1, cli_tool="opencode", model="minimax", is_default=True)
    opt2 = _make_option(option_id=2, cli_tool="opencode", model="claude-sonnet-4-6")

    with (
        patch("orch.agent_runtime.resolver._load_option") as mock_load,
        patch("orch.agent_runtime.resolver._load_option_by_cli_model") as mock_load_by_pair,
        patch("orch.agent_runtime.resolver._load_default") as mock_load_default,
    ):
        mock_load.return_value = None
        mock_load_by_pair.return_value = opt2
        mock_load_default.return_value = opt1

        step = FakeWorkflowStep(agent_runtime_option_id=None)
        item = FakeWorkItem(agent_runtime_option_id=None)
        project = FakeProjectConfig(cli_tool="opencode", model="claude-sonnet-4-6")

        result = resolve_runtime(MagicMock(), step=step, item=item, project=project)

        assert result.id == 2
        assert result.cli_tool == "opencode"
        assert result.model == "claude-sonnet-4-6"


def test_resolver_catalogue_default_fallback(caplog: pytest.LogCaptureFixture) -> None:
    """AC1: is_default=true row is used when nothing else resolves."""
    from orch.agent_runtime.resolver import resolve_runtime

    opt1 = _make_option(option_id=1, cli_tool="opencode", model="minimax", is_default=True)

    with (
        patch("orch.agent_runtime.resolver._load_option") as mock_load,
        patch("orch.agent_runtime.resolver._load_option_by_cli_model") as mock_load_by_pair,
        patch("orch.agent_runtime.resolver._load_default") as mock_load_default,
    ):
        mock_load.return_value = None
        mock_load_by_pair.return_value = None
        mock_load_default.return_value = opt1

        step = FakeWorkflowStep(agent_runtime_option_id=None)
        item = FakeWorkItem(agent_runtime_option_id=None)
        project = FakeProjectConfig(cli_tool="opencode", model="bogus-model-not-in-catalogue")

        result = resolve_runtime(MagicMock(), step=step, item=item, project=project)

        assert result.id == 1
        assert result.is_default is True


# ---------------------------------------------------------------------------
# Tests — boundary behavior
# ---------------------------------------------------------------------------


def test_resolver_skips_disabled_step_override(caplog: pytest.LogCaptureFixture) -> None:
    """Boundary: step override points to disabled row → skip, use item-level."""
    from orch.agent_runtime.resolver import resolve_runtime

    opt1 = _make_option(option_id=1, cli_tool="opencode", model="minimax", is_default=True)
    opt4 = _make_option(option_id=4, cli_tool="claude", model="claude-sonnet-4-6")
    opt99 = _make_option(option_id=99, cli_tool="opencode", model="claude-opus-4-7", enabled=False)

    with (
        patch("orch.agent_runtime.resolver._load_option") as mock_load,
        patch("orch.agent_runtime.resolver._load_default") as mock_load_default,
    ):

        def load_side_effect(session, opt_id):
            """Return load side effect."""
            opts = {1: opt1, 4: opt4, 99: opt99}
            return opts.get(opt_id)

        mock_load.side_effect = load_side_effect
        mock_load_default.return_value = opt1

        step = FakeWorkflowStep(agent_runtime_option_id=99)
        item = FakeWorkItem(agent_runtime_option_id=4)
        project = FakeProjectConfig()

        with caplog.at_level(logging.WARNING):
            result = resolve_runtime(MagicMock(), step=step, item=item, project=project)

        # Skipped disabled step override → falls back to item
        assert result.id == 4
        assert "disabled" in caplog.text.lower()


def test_resolver_skips_disabled_item_override(caplog: pytest.LogCaptureFixture) -> None:
    """Boundary: item override is disabled → skip, use project/catalogue default."""
    from orch.agent_runtime.resolver import resolve_runtime

    opt1 = _make_option(option_id=1, cli_tool="opencode", model="minimax", is_default=True)
    opt2 = _make_option(option_id=2, cli_tool="opencode", model="claude-sonnet-4-6")
    opt99 = _make_option(option_id=99, cli_tool="claude", model="claude-opus-4-7", enabled=False)

    with (
        patch("orch.agent_runtime.resolver._load_option") as mock_load,
        patch("orch.agent_runtime.resolver._load_option_by_cli_model") as mock_load_by_pair,
        patch("orch.agent_runtime.resolver._load_default") as mock_load_default,
    ):

        def load_side_effect(session, opt_id):
            """Return load side effect."""
            opts = {1: opt1, 2: opt2, 99: opt99}
            return opts.get(opt_id)

        mock_load.side_effect = load_side_effect
        mock_load_by_pair.return_value = opt2
        mock_load_default.return_value = opt1

        step = FakeWorkflowStep(agent_runtime_option_id=None)
        item = FakeWorkItem(agent_runtime_option_id=99)
        project = FakeProjectConfig(cli_tool="opencode", model="claude-sonnet-4-6")

        with caplog.at_level(logging.WARNING):
            result = resolve_runtime(MagicMock(), step=step, item=item, project=project)

        # Skipped disabled item override → falls back to project default
        assert result.id == 2
        assert "disabled" in caplog.text.lower()


def test_resolver_all_nulls_falls_to_default(caplog: pytest.LogCaptureFixture) -> None:
    """Boundary: all overrides null → catalogue default."""
    from orch.agent_runtime.resolver import resolve_runtime

    opt1 = _make_option(option_id=1, cli_tool="opencode", model="minimax", is_default=True)

    with (
        patch("orch.agent_runtime.resolver._load_option") as mock_load,
        patch("orch.agent_runtime.resolver._load_option_by_cli_model") as mock_load_by_pair,
        patch("orch.agent_runtime.resolver._load_default") as mock_load_default,
    ):
        mock_load.return_value = None
        mock_load_by_pair.return_value = None
        mock_load_default.return_value = opt1

        step = FakeWorkflowStep(agent_runtime_option_id=None)
        item = FakeWorkItem(agent_runtime_option_id=None)
        project = FakeProjectConfig()

        result = resolve_runtime(MagicMock(), step=step, item=item, project=project)

        assert result.id == 1
        assert result.is_default is True


def test_resolver_project_pair_not_in_catalogue_warns_and_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Boundary: project (cli_tool, model) not in catalogue → warning + fallback."""
    from orch.agent_runtime.resolver import resolve_runtime

    opt1 = _make_option(option_id=1, cli_tool="opencode", model="minimax", is_default=True)

    with (
        patch("orch.agent_runtime.resolver._load_option") as mock_load,
        patch("orch.agent_runtime.resolver._load_option_by_cli_model") as mock_load_by_pair,
        patch("orch.agent_runtime.resolver._load_default") as mock_load_default,
    ):
        mock_load.return_value = None
        mock_load_by_pair.return_value = None
        mock_load_default.return_value = opt1

        step = FakeWorkflowStep(agent_runtime_option_id=None)
        item = FakeWorkItem(agent_runtime_option_id=None)
        project = FakeProjectConfig(cli_tool="opencode", model="nonexistent-model")

        with caplog.at_level(logging.WARNING):
            result = resolve_runtime(MagicMock(), step=step, item=item, project=project)

        assert result.id == 1
        # No warning expected here — the project.toml lookup returns None silently,
        # falling through to the catalogue default. The warning is emitted at project
        # registration time in project_registry.py, not at runtime resolution.


def test_resolver_unpinned_project_skips_lookup_uses_catalogue_default(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A project that pins NO runtime (cli_tool/model None) must skip the
    projects.toml-lookup tier entirely and fall through to the catalogue
    default (is_default=true).

    Regression: previously the resolver defaulted an absent cli_tool to the
    literal "opencode", which silently shadowed the catalogue default (the
    "flip default to pi" migration) for every un-pinned project.
    """
    from orch.agent_runtime.resolver import resolve_runtime

    opt_pi = _make_option(option_id=7, cli_tool="pi", model="minimax/MiniMax-M3", is_default=True)

    with (
        patch("orch.agent_runtime.resolver._load_option") as mock_load,
        patch("orch.agent_runtime.resolver._load_option_by_cli_model") as mock_load_by_pair,
        patch("orch.agent_runtime.resolver._load_default") as mock_load_default,
    ):
        mock_load.return_value = None
        mock_load_default.return_value = opt_pi

        step = FakeWorkflowStep(agent_runtime_option_id=None)
        item = FakeWorkItem(agent_runtime_option_id=None)
        project = FakeProjectConfig(cli_tool=None, model=None)  # un-pinned

        result = resolve_runtime(MagicMock(), step=step, item=item, project=project)

        assert result.id == 7
        assert result.is_default is True
        # The projects.toml-lookup tier must be skipped — never queried.
        mock_load_by_pair.assert_not_called()


def test_resolver_missing_cli_tool_attr_skips_lookup(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A project object lacking cli_tool/model altogether (e.g. None project on
    a projects.toml read error) skips the lookup tier instead of defaulting to
    "opencode"."""
    from orch.agent_runtime.resolver import resolve_runtime

    opt_pi = _make_option(option_id=7, cli_tool="pi", model="minimax/MiniMax-M3", is_default=True)

    with (
        patch("orch.agent_runtime.resolver._load_option") as mock_load,
        patch("orch.agent_runtime.resolver._load_option_by_cli_model") as mock_load_by_pair,
        patch("orch.agent_runtime.resolver._load_default") as mock_load_default,
    ):
        mock_load.return_value = None
        mock_load_default.return_value = opt_pi

        step = FakeWorkflowStep(agent_runtime_option_id=None)
        item = FakeWorkItem(agent_runtime_option_id=None)

        result = resolve_runtime(MagicMock(), step=step, item=item, project=None)

        assert result.id == 7
        mock_load_by_pair.assert_not_called()
