"""CR-00062 — project_registry cli_tool allowlist tests.

Pins the behaviour added by CR-00062 S03: ``_build_project_config`` validates
``cli_tool`` against the code-only ``_VALID_CLI_TOOLS = {"opencode", "claude",
"pi"}`` allowlist. Unknown values warn-and-skip; valid values load; the
``.iw-orch.json`` fallback also goes through the allowlist.

These tests live in their own module (CR-00062 S05) so a future reader looking
at the allowlist regression net does not have to grep through the runtime
dispatch tests. The S03 sketch was carried in ``test_pi_runtime_dispatch.py``
during the implementation step; S05 promotes it to this durable file with
expanded coverage.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from orch.daemon.project_registry import _build_project_config


def _make_repo_root(tmp_path: Path, name: str) -> Path:
    repo_root = tmp_path / name
    repo_root.mkdir()
    return repo_root


# ---------------------------------------------------------------------------
# Valid cli_tool values — all three runtimes load successfully.
# ---------------------------------------------------------------------------


def test_valid_cli_tool_opencode_loads(tmp_path: Path) -> None:
    """Verifies that valid cli tool opencode loads."""
    repo_root = _make_repo_root(tmp_path, "p_opencode")
    result = _build_project_config(
        project_id="p-opencode",
        entry={"repo_root": str(repo_root), "cli_tool": "opencode"},
    )
    assert result is not None
    assert result.cli_tool == "opencode"


def test_valid_cli_tool_claude_loads(tmp_path: Path) -> None:
    """Verifies that valid cli tool claude loads."""
    repo_root = _make_repo_root(tmp_path, "p_claude")
    result = _build_project_config(
        project_id="p-claude",
        entry={"repo_root": str(repo_root), "cli_tool": "claude"},
    )
    assert result is not None
    assert result.cli_tool == "claude"


def test_valid_cli_tool_pi_loads(tmp_path: Path) -> None:
    """Verifies that valid cli tool pi loads."""
    repo_root = _make_repo_root(tmp_path, "p_pi")
    result = _build_project_config(
        project_id="p-pi",
        entry={"repo_root": str(repo_root), "cli_tool": "pi"},
    )
    assert result is not None
    assert result.cli_tool == "pi"


# ---------------------------------------------------------------------------
# Invalid cli_tool — warn and skip (returns None).
# ---------------------------------------------------------------------------


def test_invalid_cli_tool_typo_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """An invalid ``cli_tool`` value is logged as a warning naming the project
    id and the invalid value, and the project is skipped (``None`` returned).

    Matches the existing ``repo_root``-missing / nonexistent-repo skip patterns
    in ``_build_project_config``. The lenient ``else: claude form`` fall-through
    that previously silently launched claude for typos is the bug class this
    allowlist exists to prevent (see CR-00062 design doc § AC4).
    """
    repo_root = _make_repo_root(tmp_path, "bad_project")

    with caplog.at_level(logging.WARNING, logger="orch.daemon.project_registry"):
        result = _build_project_config(
            project_id="bad",
            entry={"repo_root": str(repo_root), "cli_tool": "pii"},  # typo
        )

    assert result is None
    # Warning must name the project id AND the bad value.
    assert any("'bad'" in rec.message for rec in caplog.records)
    assert any("'pii'" in rec.message for rec in caplog.records)
    assert any("invalid cli_tool" in rec.message.lower() for rec in caplog.records)


# ---------------------------------------------------------------------------
# Missing cli_tool — stays None (no pin) so the resolver uses the catalogue default.
# ---------------------------------------------------------------------------


def test_missing_cli_tool_is_none(tmp_path: Path) -> None:
    """Entries without a ``cli_tool`` key load with ``cli_tool=None`` (no pin).

    None must be ACCEPTED by the allowlist (not rejected) — a project that
    pins nothing is valid and falls through to the catalogue default at
    resolution time, instead of being hardcoded to ``opencode`` which would
    shadow the catalogue's is_default row.
    """
    repo_root = _make_repo_root(tmp_path, "p_default")
    result = _build_project_config(
        project_id="p-default",
        entry={"repo_root": str(repo_root)},  # no cli_tool key
    )
    assert result is not None
    assert result.cli_tool is None


# ---------------------------------------------------------------------------
# .iw-orch.json fallback — must ALSO go through the allowlist.
# ---------------------------------------------------------------------------


def test_iw_orch_json_cli_tool_fallback_validated(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """When ``cli_tool`` is absent from the ``projects.toml`` entry, the loader
    falls back to the value in ``.iw-orch.json``. The allowlist must apply on
    that path too — a typo in ``.iw-orch.json`` (which is closer to the
    project repo and thus more likely to drift) must be rejected the same way
    as a typo in ``projects.toml``.

    Regression risk: the allowlist check sits AFTER the
    ``entry.get("cli_tool") or iw_config.get("cli_tool", "opencode")``
    expression, so both paths feed into the same validator — but a future
    refactor that splits them would break this invariant silently. This test
    pins the joint behaviour.
    """
    repo_root = _make_repo_root(tmp_path, "iw_orch_typo")
    (repo_root / ".iw-orch.json").write_text(json.dumps({"cli_tool": "piE"}))

    with caplog.at_level(logging.WARNING, logger="orch.daemon.project_registry"):
        result = _build_project_config(
            project_id="iw-orch-typo",
            entry={"repo_root": str(repo_root)},  # no projects.toml cli_tool → falls back
        )

    assert result is None
    assert any("'piE'" in rec.message for rec in caplog.records)
    assert any("invalid cli_tool" in rec.message.lower() for rec in caplog.records)


def test_iw_orch_json_cli_tool_valid_pi_loads(tmp_path: Path) -> None:
    """The ``.iw-orch.json`` fallback path also accepts the three valid values.

    Without this companion test the prior negative test could pass for a
    spurious reason (e.g. the loader rejecting EVERY ``.iw-orch.json`` fallback).
    """
    repo_root = _make_repo_root(tmp_path, "iw_orch_pi")
    (repo_root / ".iw-orch.json").write_text(json.dumps({"cli_tool": "pi"}))

    result = _build_project_config(
        project_id="iw-orch-pi",
        entry={"repo_root": str(repo_root)},  # no projects.toml cli_tool → falls back
    )
    assert result is not None
    assert result.cli_tool == "pi"
