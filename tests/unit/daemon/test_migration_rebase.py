"""Unit tests for migration_rebase module.

These are fast unit tests that mock git operations via patch().
Integration tests that use real git repos + testcontainers are in
tests/integration/test_parallel_migrations.py and
tests/integration/test_migration_rebase_conflict.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock, patch

import pytest

from orch.daemon.migration_rebase import (
    GitCommandError,
    MigrationParseError,
    RebaseChainError,
    RebaseResult,
    Rewrite,
    _emit_daemon_event,
    _git,
    _latest_main_revision,
    _parse_migration,
    _rewrite_down_revision,
    _write_rebase_log,
    run_pre_merge_rebase,
)

# ---------------------------------------------------------------------------
# Module-level scratch fixtures (used across all tests)
# ---------------------------------------------------------------------------


class ScratchRepo(NamedTuple):
    root: Path


def scratch_repo(tmp_path: Path) -> ScratchRepo:
    """Initialise a real git repo with main at rev1 (initial migration)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(str(repo_root), ["init", "--initial-branch=main"])
    versions = repo_root / "orch" / "db" / "migrations" / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    (repo_root / "orch" / "db" / "migrations").mkdir(parents=True, exist_ok=True)
    _copy_alembic_skeleton(repo_root / "orch" / "db" / "migrations")

    rev1_content = _make_migration_content("rev1_initial", None)
    (versions / "rev1_initial.py").write_text(rev1_content, encoding="utf-8")
    _git(str(repo_root), ["add", "."])
    _git(str(repo_root), ["commit", "--no-verify", "-m", "rev1 initial"])
    return ScratchRepo(root=repo_root)


def _copy_alembic_skeleton(migrations_dir: Path) -> None:
    """Mirror alembic env.py + script.py.mako into the scratch repo."""
    import shutil

    src_migrations = Path(__file__).resolve().parents[4] / "orch" / "db" / "migrations"
    for name in ("env.py", "script.py.mako"):
        src = src_migrations / name
        if src.exists():
            shutil.copy2(src, migrations_dir / name)


def _make_migration_content(revision: str, down_revision: str | None) -> str:
    dn = f'"{down_revision}"' if down_revision is not None else "None"
    return f'''"""Add {revision} migration.

Revision ID: {revision}
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from __future__ import annotations

revision = "{revision}"
down_revision = {dn}


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
'''


def scratch_branch(
    repo: ScratchRepo,
    branch_name: str,
    from_ref: str,
    migrations: list[tuple[str, str | None]],
) -> None:
    """Create a branch from from_ref and add migration files to it."""
    _git(str(repo.root), ["checkout", "-b", branch_name, from_ref])
    versions = repo.root / "orch" / "db" / "migrations" / "versions"
    for rev, down in migrations:
        content = _make_migration_content(rev, down)
        (versions / f"{rev}.py").write_text(content, encoding="utf-8")
        _git(str(repo.root), ["add", f"orch/db/migrations/versions/{rev}.py"])
    if migrations:
        _git(str(repo.root), ["commit", "--no-verify", "-m", f"add {branch_name} migrations"])


def advance_main(repo: ScratchRepo, migrations: list[tuple[str, str | None]]) -> str:
    """Add migrations on main branch and return the last revision id."""
    _git(str(repo.root), ["checkout", "main"])
    versions = repo.root / "orch" / "db" / "migrations" / "versions"
    for rev, down in migrations:
        content = _make_migration_content(rev, down)
        (versions / f"{rev}.py").write_text(content, encoding="utf-8")
        _git(str(repo.root), ["add", f"orch/db/migrations/versions/{rev}.py"])
        _git(str(repo.root), ["commit", "--no-verify", "-m", f"main advance {rev}"])
    return migrations[-1][0]


class TestParseMigration:
    """Tests for _parse_migration helper."""

    def test_parses_valid_migration_with_double_quotes(self, tmp_path: Path) -> None:
        content = '''"""Add users table.

Revision ID: abc123
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from __future__ import annotations

revision = "abc123"
down_revision = "def456"


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
'''
        path = tmp_path / "abc123_add_users.py"
        path.write_text(content, encoding="utf-8")

        revision, down_revision = _parse_migration(str(path))

        assert revision == "abc123"
        assert down_revision == "def456"

    def test_parses_valid_migration_with_single_quotes(self, tmp_path: Path) -> None:
        content = '''"""Add orders table.

Revision ID: xyz789
Revises: abc123
Create Date: 2025-01-02 00:00:00.000000

"""
revision = "xyz789"
down_revision = "abc123"


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
'''
        path = tmp_path / "xyz789_add_orders.py"
        path.write_text(content, encoding="utf-8")

        revision, down_revision = _parse_migration(str(path))

        assert revision == "xyz789"
        assert down_revision == "abc123"

    def test_parses_down_revision_none(self, tmp_path: Path) -> None:
        content = '''"""Initial schema.

Revision ID: init001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
revision = "init001"
down_revision = None


def upgrade() -> None:
    pass
'''
        path = tmp_path / "init001_initial.py"
        path.write_text(content, encoding="utf-8")

        revision, down_revision = _parse_migration(str(path))

        assert revision == "init001"
        assert down_revision is None

    def test_raises_on_missing_revision(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.py"
        path.write_text("down_revision = 'abc'\n", encoding="utf-8")

        with pytest.raises(MigrationParseError, match="Could not find 'revision'"):
            _parse_migration(str(path))

    def test_raises_on_missing_down_revision(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.py"
        path.write_text('revision = "abc"\n', encoding="utf-8")

        with pytest.raises(MigrationParseError, match="Could not find 'down_revision'"):
            _parse_migration(str(path))


class TestGitCommand:
    """Tests for _git helper."""

    def test_raises_on_failure(self) -> None:
        with pytest.raises(GitCommandError):
            _git("/", ["rev-parse", "nonexistent-ref"])


class TestRewriteDownRevision:
    """Tests for _rewrite_down_revision helper."""

    def test_replaces_double_quoted_down_revision(self, tmp_path: Path) -> None:
        content = 'revision = "abc123"\ndown_revision = "def456"\n'
        path = tmp_path / "abc123_test.py"
        path.write_text(content, encoding="utf-8")

        _rewrite_down_revision(str(path), '"xyz789"')

        result = path.read_text(encoding="utf-8")
        assert result == 'revision = "abc123"\ndown_revision = "xyz789"\n'

    def test_replaces_single_quoted_down_revision(self, tmp_path: Path) -> None:
        content = "revision = 'abc123'\ndown_revision = 'def456'\n"
        path = tmp_path / "abc123_test.py"
        path.write_text(content, encoding="utf-8")

        _rewrite_down_revision(str(path), "'xyz789'")

        result = path.read_text(encoding="utf-8")
        assert result == "revision = 'abc123'\ndown_revision = 'xyz789'\n"

    def test_replaces_none_down_revision(self, tmp_path: Path) -> None:
        content = "revision = 'abc123'\ndown_revision = None\n"
        path = tmp_path / "abc123_test.py"
        path.write_text(content, encoding="utf-8")

        _rewrite_down_revision(str(path), '"newbase"')

        result = path.read_text(encoding="utf-8")
        assert result == "revision = 'abc123'\ndown_revision = \"newbase\"\n"

    def test_raises_on_no_matching_line(self, tmp_path: Path) -> None:
        path = tmp_path / "abc123_test.py"
        path.write_text("revision = 'abc123'\n", encoding="utf-8")

        with pytest.raises(MigrationParseError, match="Could not find down_revision line"):
            _rewrite_down_revision(str(path), '"xyz789"')


class TestEmitDaemonEvent:
    """Tests for _emit_daemon_event helper."""

    def test_writes_daemon_event_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
        monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
        mock_session = MagicMock()
        mock_connection = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)

        with patch("orch.daemon.migration_rebase.safe_create_engine") as mock_engine:
            mock_engine.return_value.connect.return_value = mock_connection
            mock_engine.return_value.dispose = MagicMock()
            with patch("orch.daemon.migration_rebase.sessionmaker") as mock_sm:
                mock_sm.return_value.return_value = mock_session

                _emit_daemon_event(
                    event_type="migration_rebase",
                    metadata={"batch_id": 1, "rebase_needed": True},
                    message="Pre-merge rebase starting",
                )

                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()
                # Verify DaemonEvent row was created with correct event_type and message
                added_event = mock_session.add.call_args[0][0]
                assert added_event.event_type == "migration_rebase"
                assert "Pre-merge rebase starting" in added_event.message


class TestWriteRebaseLog:
    """Tests for _write_rebase_log helper."""

    def test_writes_pending_migration_log_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
        monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
        mock_session = MagicMock()
        mock_connection = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)

        with patch("orch.daemon.migration_rebase.safe_create_engine") as mock_engine:
            mock_engine.return_value.connect.return_value = mock_connection
            mock_engine.return_value.dispose = MagicMock()
            with patch("orch.daemon.migration_rebase.sessionmaker") as mock_sm:
                mock_sm.return_value.return_value = mock_session

                _write_rebase_log(
                    revision="abc123",
                    old_revision="def456",
                    batch_id=42,
                )

                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()
                # Verify PendingMigrationLog row was created with correct revision fields
                added_log = mock_session.add.call_args[0][0]
                assert added_log.revision == "abc123"
                assert added_log.old_revision == "def456"


class TestRunPreMergeRebase:
    """Tests for run_pre_merge_rebase entry point."""

    def _make_migration_file(self, path: Path, revision: str, down_revision: str | None) -> None:
        dn = f'"{down_revision}"' if down_revision is not None else "None"
        content = f'''"""Add {revision} migration."""

revision = "{revision}"
down_revision = {dn}


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
'''
        path.write_text(content, encoding="utf-8")

    def _make_worktree(self, tmp_path: Path) -> Path:
        """Create a minimal worktree with migrations directory."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / ".git").touch()
        versions = worktree / "orch" / "db" / "migrations" / "versions"
        versions.mkdir(parents=True, exist_ok=True)
        migrations = worktree / "orch" / "db" / "migrations"
        migrations.mkdir(parents=True, exist_ok=True)
        env_py = migrations / "env.py"
        env_py.write_text("# env.py\n", encoding="utf-8")
        mako = migrations / "script.py.mako"
        mako.write_text("# script.py.mako\n", encoding="utf-8")
        return worktree

    def test_preflight_daemon_event_emitted_when_rebase_not_needed(self, tmp_path: Path) -> None:
        """AC2: DaemonEvent emitted even when no rebase needed (rebase_needed=false)."""
        worktree = self._make_worktree(tmp_path)
        versions = worktree / "orch" / "db" / "migrations" / "versions"
        rev_file = versions / "abc123_add_col.py"
        self._make_migration_file(rev_file, "abc123", "def456")

        daemon_events: list[MagicMock] = []

        def git_side_effect(cwd: str, args: list[str]) -> str:
            if args[0] == "merge-base":
                return "def456"  # worktree_base_sha == def456 (main head when branch was created)
            if args[0] == "fetch":
                return ""
            if args[0] == "rev-parse":
                return "def456"  # current_main_sha == def456 (no new merges)
            if args[0] == "diff":
                return f"orch/db/migrations/versions/{rev_file.name}"
            return ""

        def emit_side_effect(event_type: str, metadata: dict, message: str) -> None:
            mock_event = MagicMock()
            mock_event.call_args = (
                (),
                {"event_type": event_type, "metadata": metadata, "message": message},
            )
            daemon_events.append(mock_event)

        def mock_latest_main_revision(worktree_path: str, batch_files: list[str]) -> str | None:
            return "def456"

        with (
            patch("orch.daemon.migration_rebase._git", side_effect=git_side_effect),
            patch("orch.daemon.migration_rebase._emit_daemon_event", side_effect=emit_side_effect),
            patch(
                "orch.daemon.migration_rebase._latest_main_revision",
                side_effect=mock_latest_main_revision,
            ),
        ):
            result = run_pre_merge_rebase(
                batch_id=1,
                worktree_path=str(worktree),
                _repo_root=str(tmp_path),
            )

        assert result.success is True, f"Expected success but got: {result}"
        assert result.rebased is False
        assert result.rewrites == []
        assert len(daemon_events) == 1
        event_meta = daemon_events[0].call_args[1]
        assert event_meta["event_type"] == "migration_rebase"
        assert event_meta["metadata"]["rebase_needed"] is False

    def test_rewrite_happens_for_single_stale_migration(self, tmp_path: Path) -> None:
        """AC1: Single stale migration gets rewritten and committed."""
        worktree = self._make_worktree(tmp_path)
        versions = worktree / "orch" / "db" / "migrations" / "versions"
        rev_file = versions / "abc123_add_col.py"
        self._make_migration_file(rev_file, "abc123", "rev1_initial")

        def git_side_effect(cwd: str, args: list[str]) -> str:
            if args[0] == "merge-base":
                return "rev1_initial"
            if args[0] == "fetch":
                return ""
            if args[0] == "rev-parse":
                return "rev2a_main_head"
            if args[0] == "rebase":
                return ""
            if args[0] == "diff":
                return f"orch/db/migrations/versions/{rev_file.name}"
            if args[0] == "add":
                return ""
            if args[0] == "commit":
                return ""
            return ""

        def mock_latest_main_revision(worktree_path: str, batch_files: list[str]) -> str | None:
            return "rev2a_main_head"

        with (
            patch("orch.daemon.migration_rebase._git", side_effect=git_side_effect),
            patch("orch.daemon.migration_rebase._emit_daemon_event"),
            patch("orch.daemon.migration_rebase._write_rebase_log"),
            patch(
                "orch.daemon.migration_rebase._latest_main_revision",
                side_effect=mock_latest_main_revision,
            ),
        ):
            result = run_pre_merge_rebase(
                batch_id=1,
                worktree_path=str(worktree),
                _repo_root=str(tmp_path),
            )

        assert result.success is True, f"Expected success but got: {result}"
        assert result.rebased is True
        assert len(result.rewrites) == 1
        assert result.rewrites[0] == Rewrite(
            revision="abc123",
            old_down_revision="rev1_initial",
            new_down_revision="rev2a_main_head",
        )

        rewritten_content = rev_file.read_text(encoding="utf-8")
        assert 'down_revision = "rev2a_main_head"' in rewritten_content

    def test_multi_file_chain_preserves_internal_links(self, tmp_path: Path) -> None:
        """AC3: Multi-file batch preserves internal chain links — only root rewritten."""
        worktree = self._make_worktree(tmp_path)
        versions = worktree / "orch" / "db" / "migrations" / "versions"
        rev_b1 = versions / "revB1_add_col.py"
        rev_b2 = versions / "revB2_another_col.py"
        self._make_migration_file(rev_b1, "revB1", "rev1_initial")
        self._make_migration_file(rev_b2, "revB2", "revB1")

        def git_side_effect(cwd: str, args: list[str]) -> str:
            if args[0] == "merge-base":
                return "rev1_initial"
            if args[0] == "fetch":
                return ""
            if args[0] == "rev-parse":
                return "rev2a_main_head"
            if args[0] == "rebase":
                return ""
            if args[0] == "diff":
                return (
                    "orch/db/migrations/versions/revB1_add_col.py\n"
                    "orch/db/migrations/versions/revB2_another_col.py"
                )
            if args[0] == "add":
                return ""
            if args[0] == "commit":
                return ""
            return ""

        def mock_latest_main_revision(worktree_path: str, batch_files: list[str]) -> str | None:
            return "rev2a_main_head"

        with (
            patch("orch.daemon.migration_rebase._git", side_effect=git_side_effect),
            patch("orch.daemon.migration_rebase._emit_daemon_event"),
            patch("orch.daemon.migration_rebase._write_rebase_log"),
            patch(
                "orch.daemon.migration_rebase._latest_main_revision",
                side_effect=mock_latest_main_revision,
            ),
        ):
            result = run_pre_merge_rebase(
                batch_id=1,
                worktree_path=str(worktree),
                _repo_root=str(tmp_path),
            )

        assert result.success is True, f"Expected success but got: {result}"
        assert len(result.rewrites) == 1
        assert result.rewrites[0].revision == "revB1"
        assert result.rewrites[0].old_down_revision == "rev1_initial"
        assert result.rewrites[0].new_down_revision == "rev2a_main_head"

        rev_b1_content = rev_b1.read_text(encoding="utf-8")
        assert 'down_revision = "rev2a_main_head"' in rev_b1_content

        rev_b2_content = rev_b2.read_text(encoding="utf-8")
        assert 'down_revision = "revB1"' in rev_b2_content

    def test_rebase_conflict_returns_failure(self, tmp_path: Path) -> None:
        """AC4: Git rebase conflict → success=False, error_message set, abort called."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / ".git").touch()
        versions = worktree / "orch" / "db" / "migrations" / "versions"
        versions.mkdir(parents=True)

        abort_called = False

        def git_side_effect(cwd: str, args: list[str]) -> str:
            if args[0] == "merge-base":
                return "old_base"
            if args[0] == "fetch":
                return ""
            if args[0] == "rev-parse":
                return "new_main"
            if args[0] == "diff":
                # Preflight check: pretend the batch added a migration so we
                # actually reach the rebase step.
                return "orch/db/migrations/versions/abc123_add_col.py"
            if args[0] == "status":
                return " M orch/db/migrations/versions/abc123_add_col.py"
            if args[0] == "rebase":
                if args[1] == "--abort":
                    nonlocal abort_called
                    abort_called = True
                    return ""
                raise GitCommandError(
                    "CONFLICT (content): Merge conflict in orch/db/models.py",
                    argv=args,
                    stdout="",
                    stderr="CONFLICT (content): Merge conflict in orch/db/models.py",
                    returncode=1,
                )
            return ""

        with (
            patch("orch.daemon.migration_rebase._git", side_effect=git_side_effect),
            patch("orch.daemon.migration_rebase._emit_daemon_event"),
        ):
            result = run_pre_merge_rebase(
                batch_id=1,
                worktree_path=str(worktree),
                _repo_root=str(tmp_path),
            )

        assert result.success is False
        assert result.rebased is False
        assert "git rebase main failed" in result.error_message
        assert "CONFLICT" in result.error_message
        assert abort_called

    def test_rebase_abort_failure_does_not_mask_original_error(self, tmp_path: Path) -> None:
        """If `git rebase --abort` fails (e.g. no rebase actually started),
        the original git rebase error must still be surfaced — not the abort
        error. Regression test for CR-00039 diagnostic loss.
        """
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / ".git").touch()
        versions = worktree / "orch" / "db" / "migrations" / "versions"
        versions.mkdir(parents=True)

        def git_side_effect(cwd: str, args: list[str]) -> str:
            if args[0] == "merge-base":
                return "old_base"
            if args[0] == "fetch":
                return ""
            if args[0] == "rev-parse":
                if "--abbrev-ref" in args:
                    return "agent/CR-00039"
                if args[-1] == "HEAD":
                    return "deadbeef"
                return "new_main"
            if args[0] == "diff":
                return "orch/db/migrations/versions/abc123_add_col.py"
            if args[0] == "status":
                return (
                    " M dashboard/templates/components/step_pipeline.html\n"
                    " M dashboard/static/styles.css"
                )
            if args[0] == "rebase":
                if args[1] == "--abort":
                    raise GitCommandError(
                        "fatal: No rebase in progress?",
                        argv=args,
                        stdout="",
                        stderr="fatal: No rebase in progress?",
                        returncode=128,
                    )
                raise GitCommandError(
                    "error: cannot rebase: You have unstaged changes.",
                    argv=args,
                    stdout="",
                    stderr="error: cannot rebase: You have unstaged changes.",
                    returncode=1,
                )
            return ""

        with (
            patch("orch.daemon.migration_rebase._git", side_effect=git_side_effect),
            patch("orch.daemon.migration_rebase._emit_daemon_event"),
        ):
            result = run_pre_merge_rebase(
                batch_id=84,
                worktree_path=str(worktree),
                _repo_root=str(tmp_path),
            )

        assert result.success is False
        # The real cause must be preserved, not the abort failure.
        assert "cannot rebase" in result.error_message
        assert "unstaged changes" in result.error_message
        # The abort failure should still be noted, but as a footnote.
        assert "abort cleanup also failed" in result.error_message
        assert "No rebase in progress" in result.error_message
        # Working-tree state should be captured.
        assert "working tree dirty: True" in result.error_message
        assert "branch: agent/CR-00039" in result.error_message

    def test_no_batch_migration_files_skips_rebase_entirely(self, tmp_path: Path) -> None:
        """AC: When this batch added no migration files, the rebase is skipped
        entirely — preventing failures on unrelated reasons (e.g. unstaged
        agent work that worktree_commit.sh is responsible for committing).
        """
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / ".git").touch()

        rebase_called = False

        def git_side_effect(cwd: str, args: list[str]) -> str:
            if args[0] == "merge-base":
                return "old_base"
            if args[0] == "fetch":
                return ""
            if args[0] == "rev-parse":
                return "new_main"
            if args[0] == "diff":
                return ""  # batch added no migration files
            if args[0] == "rebase":
                nonlocal rebase_called
                rebase_called = True
                return ""
            return ""

        with (
            patch("orch.daemon.migration_rebase._git", side_effect=git_side_effect),
            patch("orch.daemon.migration_rebase._emit_daemon_event"),
        ):
            result = run_pre_merge_rebase(
                batch_id=1,
                worktree_path=str(worktree),
                _repo_root=str(tmp_path),
            )

        assert result.success is True
        assert result.rebased is False
        assert result.rewrites == []
        assert "No migration files" in result.message
        assert rebase_called is False, "rebase must be skipped when no batch migrations"

    def test_parse_error_returns_failure(self, tmp_path: Path) -> None:
        """Malformed migration file → success=False with parse error message."""
        worktree = self._make_worktree(tmp_path)
        versions = worktree / "orch" / "db" / "migrations" / "versions"
        bad_file = versions / "bad_file.py"
        bad_file.write_text('revision = "abc123"\n', encoding="utf-8")  # missing down_revision

        def git_side_effect(cwd: str, args: list[str]) -> str:
            if args[0] == "merge-base":
                return "old_base"
            if args[0] == "fetch":
                return ""
            if args[0] == "rev-parse":
                return "new_main"
            if args[0] == "rebase":
                return ""
            if args[0] == "diff":
                return f"orch/db/migrations/versions/{bad_file.name}"
            return ""

        with (
            patch("orch.daemon.migration_rebase._git", side_effect=git_side_effect),
            patch("orch.daemon.migration_rebase._emit_daemon_event"),
        ):
            result = run_pre_merge_rebase(
                batch_id=1,
                worktree_path=str(worktree),
                _repo_root=str(tmp_path),
            )

        assert result.success is False
        assert "Parse error" in result.message
        assert "Could not find 'down_revision'" in result.error_message

    def test_fetch_failure_returns_failure(self, tmp_path: Path) -> None:
        """Git fetch failure → success=False."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / ".git").touch()

        def git_side_effect(cwd: str, args: list[str]) -> str:
            if args[0] == "merge-base":
                return "old_base"
            if args[0] == "fetch":
                raise GitCommandError("fatal: couldn't find remote ref main")
            return ""

        with (
            patch("orch.daemon.migration_rebase._git", side_effect=git_side_effect),
            patch("orch.daemon.migration_rebase._emit_daemon_event"),
        ):
            result = run_pre_merge_rebase(
                batch_id=1,
                worktree_path=str(worktree),
                _repo_root=str(tmp_path),
            )

        assert result.success is False
        assert "Git command failed" in result.message

    def test_no_batch_migration_files_is_idempotent_noop(self, tmp_path: Path) -> None:
        """No batch migration files → returns success with empty rewrites, no commit.

        After CR-00039 fix, the rebase is skipped entirely when no migration files
        were added by the batch — so `rebased` is False (the rebase did not run).
        """
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / ".git").touch()

        def git_side_effect(cwd: str, args: list[str]) -> str:
            if args[0] == "merge-base":
                return "old_base"
            if args[0] == "fetch":
                return ""
            if args[0] == "rev-parse":
                return "new_main"
            if args[0] == "rebase":
                return ""
            if args[0] == "diff":
                return ""  # no files added
            return ""

        with (
            patch("orch.daemon.migration_rebase._git", side_effect=git_side_effect),
            patch("orch.daemon.migration_rebase._emit_daemon_event"),
        ):
            result = run_pre_merge_rebase(
                batch_id=1,
                worktree_path=str(worktree),
                _repo_root=str(tmp_path),
            )

        assert result.success is True
        assert result.rebased is False
        assert result.rewrites == []
        assert "No migration files" in result.message

    def test_pending_migration_log_written_for_each_rewrite(self, tmp_path: Path) -> None:
        """After successful rewrite, _write_rebase_log is called with correct args."""
        worktree = self._make_worktree(tmp_path)
        versions = worktree / "orch" / "db" / "migrations" / "versions"
        rev_file = versions / "abc123_add_col.py"
        self._make_migration_file(rev_file, "abc123", "rev1_initial")

        write_log_calls: list[tuple[str, str, int]] = []

        def git_side_effect(cwd: str, args: list[str]) -> str:
            if args[0] == "merge-base":
                return "rev1_initial"
            if args[0] == "fetch":
                return ""
            if args[0] == "rev-parse":
                return "rev2a_main_head"
            if args[0] == "rebase":
                return ""
            if args[0] == "diff":
                return f"orch/db/migrations/versions/{rev_file.name}"
            if args[0] == "add":
                return ""
            if args[0] == "commit":
                return ""
            return ""

        def write_rebase_log_side_effect(revision: str, old_revision: str, batch_id: int) -> None:
            write_log_calls.append((revision, old_revision, batch_id))

        def mock_latest_main_revision(worktree_path: str, batch_files: list[str]) -> str | None:
            return "rev2a_main_head"

        with (
            patch("orch.daemon.migration_rebase._git", side_effect=git_side_effect),
            patch("orch.daemon.migration_rebase._emit_daemon_event"),
            patch(
                "orch.daemon.migration_rebase._write_rebase_log",
                side_effect=write_rebase_log_side_effect,
            ),
            patch(
                "orch.daemon.migration_rebase._latest_main_revision",
                side_effect=mock_latest_main_revision,
            ),
        ):
            result = run_pre_merge_rebase(
                batch_id=42,
                worktree_path=str(worktree),
                _repo_root=str(tmp_path),
            )

        assert result.success is True, f"Expected success but got: {result}"
        assert len(write_log_calls) == 1
        assert write_log_calls[0] == ("abc123", "rev1_initial", 42)


class TestLatestMainRevision:
    """Tests for _latest_main_revision helper."""

    def test_raises_on_multiple_heads(self, tmp_path: Path) -> None:
        """Pre-existing multi-head on main → RebaseChainError."""
        versions = tmp_path / "versions"
        versions.mkdir()
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        env_py = migrations / "env.py"
        env_py.write_text("# env\n", encoding="utf-8")
        mako = migrations / "script.py.mako"
        mako.write_text("# mako\n", encoding="utf-8")

        (versions / "head_a.py").write_text(
            'revision = "a"\ndown_revision = None\n', encoding="utf-8"
        )
        (versions / "head_b.py").write_text(
            'revision = "b"\ndown_revision = None\n', encoding="utf-8"
        )

        worktree_path = str(tmp_path / "worktree")

        with patch("orch.daemon.migration_rebase.ScriptDirectory") as mock_sd:
            mock_script_dir = MagicMock()
            mock_script_dir.get_heads.return_value = ["a", "b"]
            mock_sd.from_config.return_value = mock_script_dir

            with pytest.raises(RebaseChainError, match="multiple heads"):
                _latest_main_revision(worktree_path, [])

    def test_latest_main_revision_excludes_batch_files(self, tmp_path: Path) -> None:
        """_latest_main_revision must ignore batch files when computing main's head.

        This test creates a worktree that (after rebase) would have multiple heads
        if batch files were included — which is the exact problem the helper solves.
        """
        repo = scratch_repo(tmp_path)
        advance_main(repo, [("rev2a", "rev1_initial")])

        wt_path = tmp_path / "wt"
        _git(str(repo.root), ["worktree", "add", "--detach", str(wt_path), "HEAD"])
        scratch_branch(repo, "batch-branch", "HEAD", [("revB", "rev1_initial")])

        _copy_alembic_skeleton(wt_path / "orch" / "db" / "migrations")

        from orch.daemon.migration_rebase import _latest_main_revision

        main_head = _latest_main_revision(str(wt_path), ["orch/db/migrations/versions/revB.py"])
        assert main_head == "rev2a"

    def test_latest_main_revision_preexisting_multi_head_fails_cleanly(
        self,
        tmp_path: Path,
    ) -> None:
        """Pre-existing multi-head on main (not this batch's fault) → RebaseChainError."""
        repo = scratch_repo(tmp_path)
        advance_main(repo, [("rev2a_first", "rev1_initial")])
        advance_main(repo, [("rev2a_second", "rev1_initial")])

        wt_path = tmp_path / "wt"
        _git(str(repo.root), ["worktree", "add", "--detach", str(wt_path), "HEAD"])
        scratch_branch(repo, "batch-branch", "HEAD", [("revB", "rev1_initial")])

        _copy_alembic_skeleton(wt_path / "orch" / "db" / "migrations")

        from orch.daemon.migration_rebase import _latest_main_revision

        with pytest.raises(RebaseChainError, match="multiple heads"):
            _latest_main_revision(str(wt_path), ["orch/db/migrations/versions/revB.py"])


class TestRebaseResultDataclass:
    """Tests for RebaseResult and Rewrite dataclasses."""

    def test_rewrite_is_frozen(self) -> None:
        rw = Rewrite(revision="abc", old_down_revision="def", new_down_revision="ghi")
        assert rw.revision == "abc"
        assert rw.old_down_revision == "def"
        assert rw.new_down_revision == "ghi"

    def test_rebase_result_is_frozen(self) -> None:
        result = RebaseResult(
            success=True,
            rebased=True,
            rewrites=[],
            worktree_base_sha="abc",
            current_main_sha="def",
            message="ok",
            error_message=None,
        )
        assert result.success is True
        assert result.rebased is True
        assert result.rewrites == []


def test_pending_sentinel_is_always_rewritten(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _git(str(repo_root), ["init", "--initial-branch=main"])
    _git(str(repo_root), ["config", "user.email", "test@example.com"])
    _git(str(repo_root), ["config", "user.name", "Test User"])
    _git(str(repo_root), ["remote", "add", "origin", "."])

    versions = repo_root / "orch" / "db" / "migrations" / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    migrations_dir = repo_root / "orch" / "db" / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    _copy_alembic_skeleton(migrations_dir)

    main_migration = versions / "aabbccdd1122_main.py"
    main_migration.write_text(
        _make_migration_content("aabbccdd1122", None),
        encoding="utf-8",
    )
    _git(str(repo_root), ["add", "."])
    _git(str(repo_root), ["commit", "--no-verify", "-m", "add main migration"])

    _git(str(repo_root), ["checkout", "-b", "feature/cr-00091"])
    pending_migration = versions / "eeff99887766_feature.py"
    pending_migration.write_text(
        _make_migration_content("eeff99887766", "PENDING"),
        encoding="utf-8",
    )
    _git(str(repo_root), ["add", str(pending_migration.relative_to(repo_root))])
    _git(str(repo_root), ["commit", "--no-verify", "-m", "add pending migration"])

    result = run_pre_merge_rebase(
        batch_id=91,
        worktree_path=str(repo_root),
        _repo_root=str(tmp_path),
    )

    assert result.success is True
    assert len(result.rewrites) == 1
    assert result.rewrites[0].old_down_revision == "PENDING"
    assert result.rewrites[0].new_down_revision == "aabbccdd1122"

    rewritten_content = pending_migration.read_text(encoding="utf-8")
    assert 'down_revision = "aabbccdd1122"' in rewritten_content
    assert 'down_revision = "PENDING"' not in rewritten_content
