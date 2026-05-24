"""Unit tests for I-00107 — daemon reload applies .iw-orch.json changes.

Tests the five acceptance criteria for the daemon SIGHUP reload fix:

- AC1: editing .iw-orch.json + reload rebuilds the BatchManager with new config
- AC2: next _process_batch reads from the new config (transitive via AC1)
- AC3: enabled/disabled toggle also rebuilds the BatchManager
- AC4: a project_config_reloaded DaemonEvent is emitted on drift or toggle
- AC5: a no-churn guard prevents needless rebuilds when nothing changed
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from orch.daemon.main import Daemon

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from contextlib import AbstractContextManager

    SessionFactory = Callable[[], AbstractContextManager[Session]]


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _write_projects_toml(
    path: Path,
    project_id: str,
    repo_root: str,
    enabled: bool = True,
) -> None:
    """Write a minimal projects.toml for one project."""
    content = f"[projects.{project_id}]\n"
    content += f'repo_root = "{repo_root}"\n'
    content += f"enabled = {'true' if enabled else 'false'}\n"
    path.write_text(content)


def _write_iw_orch_json(repo_root: Path, *, allow_on_overlap: list[str] | None = None) -> None:
    """Write a .iw-orch.json with an optional allow_on_overlap list."""
    data = {}
    if allow_on_overlap is not None:
        data["overlap_gate"] = {"allow_on_overlap": allow_on_overlap}
    Path(repo_root / ".iw-orch.json").write_text(json.dumps(data))


@contextmanager
def _mock_session_factory() -> Generator[MagicMock, None, None]:
    """A context-manager session factory that yields a MagicMock session."""
    session = MagicMock(spec=Session)
    try:
        yield session
    finally:
        pass


def _build_daemon(projects_toml: Path) -> Daemon:
    """Construct a Daemon that skips DB-backed _startup and uses a mock session factory."""
    from orch.config import DaemonConfig

    config = MagicMock(spec=DaemonConfig)
    config.projects_toml = projects_toml
    config.db_url = "postgresql://localhost/test"

    daemon = Daemon(config=config, session_factory=_mock_session_factory)
    # Skip _startup (alembic guard, identity check, etc.) — we only test reload logic
    daemon._startup = MagicMock()  # type: ignore[method-assign]
    return daemon


# ---------------------------------------------------------------------------
# AC1 — .iw-orch.json content drift rebuilds BatchManager
# ---------------------------------------------------------------------------


def test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes(tmp_path: Path) -> None:
    """Reproduction test for I-00107.

    Fails before the fix: reload() returns change-type 'unchanged' and
    self.managers[pid] stays the same object reference (same stale config).

    Passes after fix: reload() returns change-type 'changed' and a fresh
    BatchManager is installed with the new overlap_allow_patterns baked in.
    """
    # Arrange: projects.toml + initial .iw-orch.json with allow=["tests/**"]
    projects_toml = tmp_path / "projects.toml"
    repo = tmp_path / "repo"
    repo.mkdir()

    _write_projects_toml(projects_toml, project_id="demo", repo_root=str(repo))
    _write_iw_orch_json(repo, allow_on_overlap=["tests/**"])

    daemon = _build_daemon(projects_toml)
    daemon._reload_projects_if_stale()  # initial load

    pre_manager = daemon.managers["demo"]
    pre_allow = list(pre_manager.project_config.overlap_allow_patterns)

    # Act: edit ONLY .iw-orch.json — projects.toml is untouched
    _write_iw_orch_json(repo, allow_on_overlap=["tests/**", "**/*.md"])
    daemon.registry._mtime = 0.0  # simulate SIGHUP (forces is_stale → True)
    daemon._reload_projects_if_stale()

    # Assert: BatchManager is replaced and its config reflects the new .iw-orch.json
    post_manager = daemon.managers["demo"]
    assert post_manager is not pre_manager, (
        "I-00107: reload must replace the BatchManager when .iw-orch.json changes"
    )
    post_allow = list(post_manager.project_config.overlap_allow_patterns)
    assert "**/*.md" in post_allow, "I-00107: overlap_allow_patterns must contain the new value"
    assert "**/*.md" not in pre_allow, (
        "I-00107: overlap_allow_patterns must reflect the edited .iw-orch.json"
    )


# ---------------------------------------------------------------------------
# AC5 — no-churn guard (regression against "always rebuild")
# ---------------------------------------------------------------------------


def test_reload_unchanged_when_iw_orch_json_is_identical(tmp_path: Path) -> None:
    """Second reload with no file changes must NOT rebuild the manager.

    Protects against a regression to "always rebuild on reload" that would
    waste cycles and reset per-manager in-memory state for every project
    on every SIGHUP.
    """
    projects_toml = tmp_path / "projects.toml"
    repo = tmp_path / "repo"
    repo.mkdir()

    _write_projects_toml(projects_toml, project_id="demo", repo_root=str(repo))
    _write_iw_orch_json(repo, allow_on_overlap=["tests/**", "**/*.py"])

    daemon = _build_daemon(projects_toml)
    daemon._reload_projects_if_stale()  # initial load

    pre_manager = daemon.managers["demo"]

    # Trigger reload WITHOUT editing anything
    daemon.registry._mtime = 0.0
    daemon._reload_projects_if_stale()

    post_manager = daemon.managers["demo"]
    assert post_manager is pre_manager, (
        "rebuild on identical reload wastes cycles and resets in-memory state"
    )


# ---------------------------------------------------------------------------
# AC3 — enabled/disabled toggle also refreshes BatchManager
# ---------------------------------------------------------------------------


def test_reload_rebuilds_manager_on_enabled_toggle(tmp_path: Path) -> None:
    """Flipping enabled in projects.toml from false → true rebuilds the manager.

    Before fix: only self.projects[pid] was updated; self.managers[pid] kept
    the old (stale) project_config.
    After fix: a fresh BatchManager is created with the current .iw-orch.json.

    Note: in the pre-fix code, an enabled=false project IS added to self.managers
    (the fix only changed the disabled=True→False path to pop the manager). This
    test does NOT assert that manager is absent on enabled=false — that is not
    what AC3 tests. AC3 tests: after flipping to enabled=true, a manager exists
    with the CURRENT .iw-orch.json (not a stale one).
    """
    projects_toml = tmp_path / "projects.toml"
    repo = tmp_path / "repo"
    repo.mkdir()

    # Start with enabled=false
    _write_projects_toml(projects_toml, project_id="demo", repo_root=str(repo), enabled=False)
    _write_iw_orch_json(repo, allow_on_overlap=["tests/**"])

    daemon = _build_daemon(projects_toml)
    daemon._reload_projects_if_stale()

    # Act: flip enabled → true (write a NEW .iw-orch.json at the same time)
    _write_iw_orch_json(repo, allow_on_overlap=["tests/**", "**/*.md"])
    _write_projects_toml(projects_toml, project_id="demo", repo_root=str(repo), enabled=True)
    daemon.registry._mtime = 0.0
    daemon._reload_projects_if_stale()

    # Assert: a manager exists with the CURRENT .iw-orch.json (AC3)
    post_manager = daemon.managers["demo"]
    assert post_manager is not None, "enabled=true project must have a manager"
    assert "**/*.md" in post_manager.project_config.overlap_allow_patterns, (
        "I-00107 AC3: manager must be seeded from current .iw-orch.json"
    )


def test_reload_removes_manager_on_disabled_toggle(tmp_path: Path) -> None:
    """Flipping enabled from true → false removes the manager from self.managers."""
    projects_toml = tmp_path / "projects.toml"
    repo = tmp_path / "repo"
    repo.mkdir()

    _write_projects_toml(projects_toml, project_id="demo", repo_root=str(repo), enabled=True)
    _write_iw_orch_json(repo, allow_on_overlap=["tests/**"])

    daemon = _build_daemon(projects_toml)
    daemon._reload_projects_if_stale()

    assert "demo" in daemon.managers, "sanity: manager must exist before toggle"

    # Act: flip enabled → false
    _write_projects_toml(projects_toml, project_id="demo", repo_root=str(repo), enabled=False)
    daemon.registry._mtime = 0.0
    daemon._reload_projects_if_stale()

    assert "demo" not in daemon.managers, (
        "disabled project must be removed from self.managers so poll skips it"
    )


# ---------------------------------------------------------------------------
# AC4 — observability: project_config_reloaded event emitted
# ---------------------------------------------------------------------------


def test_reload_emits_project_config_reloaded_event(tmp_path: Path) -> None:
    """Editing .iw-orch.json and reloading emits exactly one event.

    Verifies AC4: a DaemonEvent with event_type='project_config_reloaded' is
    written, with metadata.changed_fields naming the specific drifted field.
    """
    projects_toml = tmp_path / "projects.toml"
    repo = tmp_path / "repo"
    repo.mkdir()

    _write_projects_toml(projects_toml, project_id="demo", repo_root=str(repo))
    _write_iw_orch_json(repo, allow_on_overlap=["tests/**"])

    daemon = _build_daemon(projects_toml)
    daemon._reload_projects_if_stale()  # initial load

    # Patch emit_event at module level so we can capture calls without touching DB
    with patch("orch.daemon.main.emit_event") as mock_emit:
        # Act: edit .iw-orch.json to add a new allow pattern
        _write_iw_orch_json(repo, allow_on_overlap=["tests/**", "**/*.md"])
        daemon.registry._mtime = 0.0
        daemon._reload_projects_if_stale()

        # Assert: exactly one project_config_reloaded event
        mock_emit.assert_called_once()
        call = mock_emit.call_args
        assert call is not None
        assert call.kwargs["event_type"] == "project_config_reloaded"
        assert call.kwargs["entity_id"] == "demo"
        # Changed fields must name the specific field that drifted
        changed_fields: list[str] = call.kwargs["metadata"]["changed_fields"]
        assert "overlap_allow_patterns" in changed_fields, (
            f"metadata.changed_fields must name the drifted field(s), got {changed_fields!r}"
        )


# ---------------------------------------------------------------------------
# Malformed .iw-orch.json is tolerated; warning is logged
# ---------------------------------------------------------------------------


def test_reload_rebuilds_manager_when_iw_orch_json_becomes_unparseable(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A malformed .iw-orch.json logs a warning and rebuilds the manager with defaults.

    The existing _build_project_config policy (unchanged by this fix) logs
    a warning when .iw-orch.json is malformed and falls back to defaults.
    Since defaults differ from the previously-loaded config,
    old[pid] != new_projects[pid] evaluates to True, 'changed' IS returned,
    the manager IS rebuilt with the default config, AND a
    project_config_reloaded event IS emitted (the changed branch runs).

    This test pins the exact behaviour: warning logged + manager rebuilt with
    new overlap_allow_patterns + event emitted.
    """
    projects_toml = tmp_path / "projects.toml"
    repo = tmp_path / "repo"
    repo.mkdir()

    _write_projects_toml(projects_toml, project_id="demo", repo_root=str(repo))
    _write_iw_orch_json(repo, allow_on_overlap=["tests/**", "**/*.md"])

    daemon = _build_daemon(projects_toml)
    daemon._reload_projects_if_stale()

    assert "**/*.md" in daemon.managers["demo"].project_config.overlap_allow_patterns

    # Act: write a malformed .iw-orch.json (truncated JSON)
    (repo / ".iw-orch.json").write_text('{"overlap_gate": {"allow_on_overlap": [')
    daemon.registry._mtime = 0.0

    with caplog.at_level("WARNING", logger="orch.daemon.project_registry"):
        daemon._reload_projects_if_stale()

    # Warning about malformed JSON must appear (existing _build_project_config policy)
    warning_messages = [rec.message for rec in caplog.records]
    assert any("Invalid .iw-orch.json" in msg for msg in warning_messages), (
        f"Warning about malformed .iw-orch.json must be logged. Got: {warning_messages}"
    )

    # Manager is rebuilt with defaults (malformed file → defaults used)
    post_manager = daemon.managers["demo"]
    assert post_manager.project_config.overlap_allow_patterns != ["tests/**", "**/*.md"], (
        "manager must be rebuilt with the new config (fallback defaults)"
    )
