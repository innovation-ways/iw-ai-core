"""CR-00024 AC1/AC2/AC3: per-gate timeout defaults override the per-step-type bucket.

Tests the new `step` keyword argument to `get_timeout` that consults
`step.gate` for QV steps before falling through to the legacy 600s bucket.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from orch.daemon.project_registry import ProjectConfig
from orch.daemon.step_monitor import (
    PLATFORM_TIMEOUT_DEFAULTS,
    QV_GATE_TIMEOUT_DEFAULTS,
    get_timeout,
)


def _project_config(timeout_overrides: dict | None = None) -> ProjectConfig:
    config: dict = {}
    if timeout_overrides:
        config["timeout_overrides"] = timeout_overrides
    return ProjectConfig(
        id="test_proj",
        display_name="Test",
        repo_root="/nonexistent",
        enabled=True,
        cli_tool="opencode",
        worktree_base=".worktrees",
        config=config,
    )


def _step(gate: str | None) -> MagicMock:
    """Build a minimal WorkflowStep-like mock exposing only `gate`."""
    s = MagicMock()
    s.gate = gate
    return s


# ---------------------------------------------------------------------------
# AC1 — per-gate defaults override the legacy 600s quality_validation bucket
# ---------------------------------------------------------------------------


def test_integration_tests_gate_returns_1200_not_600() -> None:
    """AC1: gate=integration-tests returns 1200s, not the legacy 600s."""
    project_config = _project_config()
    step = _step(gate="integration-tests")

    result = get_timeout(project_config, "quality_validation", step=step)

    assert result == 1200
    assert result != PLATFORM_TIMEOUT_DEFAULTS["quality_validation"]


def test_lint_gate_returns_120() -> None:
    """AC1: gate=lint returns 120s."""
    project_config = _project_config()
    step = _step(gate="lint")

    result = get_timeout(project_config, "quality_validation", step=step)

    assert result == 120


def test_format_gate_returns_120() -> None:
    project_config = _project_config()
    step = _step(gate="format")
    assert get_timeout(project_config, "quality_validation", step=step) == 120


def test_typecheck_gate_returns_240() -> None:
    project_config = _project_config()
    step = _step(gate="typecheck")
    assert get_timeout(project_config, "quality_validation", step=step) == 240


def test_unit_tests_gate_returns_300() -> None:
    project_config = _project_config()
    step = _step(gate="unit-tests")
    assert get_timeout(project_config, "quality_validation", step=step) == 300


def test_browser_gate_returns_1800() -> None:
    project_config = _project_config()
    step = _step(gate="browser")
    assert get_timeout(project_config, "quality_validation", step=step) == 1800


def test_all_qv_gate_defaults_are_consulted() -> None:
    """Sanity: every key in QV_GATE_TIMEOUT_DEFAULTS resolves to that value."""
    project_config = _project_config()
    for gate, expected_secs in QV_GATE_TIMEOUT_DEFAULTS.items():
        step = _step(gate=gate)
        assert get_timeout(project_config, "quality_validation", step=step) == expected_secs, (
            f"gate {gate!r} did not resolve to {expected_secs}"
        )


# ---------------------------------------------------------------------------
# AC2 — legacy NULL-gate rows fall through to the per-step-type bucket
# ---------------------------------------------------------------------------


def test_legacy_null_gate_falls_through_to_quality_validation_default() -> None:
    """AC2: a row with gate=NULL keeps the existing 600s default."""
    project_config = _project_config()
    step = _step(gate=None)

    result = get_timeout(project_config, "quality_validation", step=step)

    assert result == PLATFORM_TIMEOUT_DEFAULTS["quality_validation"]
    assert result == 600


def test_no_step_argument_falls_through_to_quality_validation_default() -> None:
    """AC2: legacy callers that don't pass `step` keep working."""
    project_config = _project_config()

    result = get_timeout(project_config, "quality_validation")

    assert result == PLATFORM_TIMEOUT_DEFAULTS["quality_validation"]


def test_unknown_gate_falls_through_to_per_type_bucket() -> None:
    """A gate name not in the dict falls through to the type bucket — safe fallback."""
    project_config = _project_config()
    step = _step(gate="some-future-gate-not-in-dict")

    result = get_timeout(project_config, "quality_validation", step=step)

    assert result == PLATFORM_TIMEOUT_DEFAULTS["quality_validation"]


# ---------------------------------------------------------------------------
# AC3 — explicit overrides still win
# ---------------------------------------------------------------------------


def test_step_config_override_beats_gate_default() -> None:
    """AC3: explicit step-level timeout wins over the gate default."""
    project_config = _project_config()
    step = _step(gate="integration-tests")
    step_config = {"timeout_secs": 1500}

    result = get_timeout(project_config, "quality_validation", step_config=step_config, step=step)

    assert result == 1500


def test_project_override_beats_gate_default() -> None:
    """AC3: project-level override wins over the gate default."""
    project_config = _project_config(timeout_overrides={"quality_validation": 1234})
    step = _step(gate="integration-tests")

    result = get_timeout(project_config, "quality_validation", step=step)

    assert result == 1234


def test_step_config_beats_project_and_gate() -> None:
    """All three override layers stacked — step_config wins."""
    project_config = _project_config(timeout_overrides={"quality_validation": 1234})
    step = _step(gate="integration-tests")
    step_config = {"timeout_secs": 555}

    result = get_timeout(project_config, "quality_validation", step_config=step_config, step=step)

    assert result == 555


# ---------------------------------------------------------------------------
# Defensive — non-QV step types ignore the gate column
# ---------------------------------------------------------------------------


def test_non_qv_step_with_gate_value_uses_step_type_bucket() -> None:
    """An implementation step is not a QV step; its gate (if somehow set) is fine
    to read but the gate-default lookup is gate-keyed not step-type-keyed —
    if the gate isn't in QV_GATE_TIMEOUT_DEFAULTS we fall through, which is
    the documented contract for unknown gates."""
    project_config = _project_config()
    step = _step(gate="some-impl-flavor")  # not in dict

    result = get_timeout(project_config, "implementation", step=step)

    assert result == PLATFORM_TIMEOUT_DEFAULTS["implementation"]
