"""Migration-rebase phase — pre-Phase-1 step that rewrites stale down_revisions.

Runs inside merge_queue._merge_item's serial critical section, before the 3-phase
migration pipeline (dry_run / apply / rollback). Prevents multi-head alembic
failures that arise when two parallel batches generate migrations off the same
main head.

Responsibilities:
- git fetch origin main; git rebase main in the batch's worktree
- Identify the batch's own migration files (files added by this branch)
- If any file's down_revision is stale (not pointing at main's current head),
  rewrite it and commit the edit
- Emit a DaemonEvent(event_type='migration_rebase') with preflight metadata
- Write a PendingMigrationLog(phase='rebase') row for each rewrite

Integration points:
- merge_queue.py — calls run_pre_merge_rebase before run_pre_merge_dry_run
- safe_migrate.py — shares PendingMigrationLog table (phase='rebase' now allowed, CR-00021)
- models.py — BatchItemStatus.migration_rebase_failed is the failure terminal
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy.orm import Session, sessionmaker

from orch.config import get_db_url
from orch.db.models import DaemonEvent, PendingMigrationLog
from orch.db.safe_migrate import _is_test_context_active
from orch.db.session import safe_create_engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GitCommandError(RuntimeError):
    """Raised when a git subprocess returns non-zero.

    Carries the full command, stdout, and stderr so failure callers can surface
    the real diagnostic instead of just a one-line stderr summary.
    """

    def __init__(
        self,
        message: str,
        *,
        argv: list[str] | None = None,
        stdout: str = "",
        stderr: str = "",
        returncode: int | None = None,
    ) -> None:
        super().__init__(message)
        self.argv = list(argv) if argv is not None else []
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    def diagnostic_block(self) -> str:
        """Return a formatted multi-line block for inclusion in error messages."""
        lines: list[str] = []
        if self.argv:
            lines.append(f"$ git {' '.join(self.argv)}")
        if self.returncode is not None:
            lines.append(f"  exit code: {self.returncode}")
        if self.stdout:
            lines.append("  --- stdout ---")
            lines.append(self.stdout.rstrip())
        if self.stderr:
            lines.append("  --- stderr ---")
            lines.append(self.stderr.rstrip())
        return "\n".join(lines)


class MigrationParseError(RuntimeError):
    """Raised when a batch migration file cannot be parsed."""


class RebaseChainError(RuntimeError):
    """Raised when the batch's own migration files do not form a single chain."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rewrite:
    """A single down_revision rewrite performed during the pre-merge rebase.

    Attributes:
        revision: The Alembic revision ID whose down_revision was rewritten.
        old_down_revision: The stale down_revision value before rewriting.
        new_down_revision: The correct down_revision value after rewriting.
    """

    revision: str
    old_down_revision: str
    new_down_revision: str


@dataclass(frozen=True)
class RebaseResult:
    """Result of :func:`run_pre_merge_rebase`.

    Attributes:
        success: True when the rebase and all rewrites succeeded.
        rebased: True when a ``git rebase main`` was actually executed.
        rewrites: List of down_revision rewrites performed.
        worktree_base_sha: SHA of the merge-base between HEAD and origin/main.
        current_main_sha: Current HEAD SHA of origin/main.
        message: Short human-readable summary.
        error_message: Detailed diagnostic on failure, or None on success.
    """

    success: bool
    rebased: bool
    rewrites: list[Rewrite]
    worktree_base_sha: str | None
    current_main_sha: str | None
    message: str
    error_message: str | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _git(cwd: str, args: list[str]) -> str:
    """Run a git subprocess and return stdout. Raises GitCommandError on non-zero exit."""
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise GitCommandError(
            result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}",
            argv=args,
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )
    return result.stdout.strip()


def _capture_worktree_state(worktree_path: str) -> dict[str, Any]:
    """Best-effort capture of git worktree state for failure diagnostics.

    Never raises — returns whatever it could collect plus per-key error strings.
    """
    state: dict[str, Any] = {}
    fields: dict[str, list[str]] = {
        "branch": ["rev-parse", "--abbrev-ref", "HEAD"],
        "head_sha": ["rev-parse", "HEAD"],
        "origin_main_sha": ["rev-parse", "origin/main"],
        "status_porcelain": ["status", "--porcelain"],
    }
    for key, argv in fields.items():
        try:
            state[key] = _git(worktree_path, argv)
        except GitCommandError as exc:
            state[key] = None
            state[f"{key}_error"] = str(exc)
    # Detect the more obvious cases up-front for the reader
    porcelain = state.get("status_porcelain") or ""
    state["dirty"] = bool(porcelain.strip())
    return state


def _parse_migration(path: str) -> tuple[str, str | None]:
    """Parse revision and down_revision from a migration file.

    Returns (revision, down_revision). down_revision is None only when the
    file literally contains ``down_revision = None``.
    Raises MigrationParseError on parse failure.
    """
    content = Path(path).read_text(encoding="utf-8")

    rev_match = re.search(
        r"^\s*revision(?:\s*:\s*[^=]+)?\s*=\s*['\"]([^'\"]+)['\"]", content, re.MULTILINE
    )
    if not rev_match:
        raise MigrationParseError(f"Could not find 'revision' in {path}")
    revision = rev_match.group(1)

    down_match = re.search(
        r"^\s*down_revision(?:\s*:\s*[^=]+)?\s*=\s*([^\s#]+)", content, re.MULTILINE
    )
    if down_match:
        raw = down_match.group(1)
        if raw == "None":
            return revision, None
        return revision, _strip_quotes(raw)

    raise MigrationParseError(f"Could not find 'down_revision' in {path}")


def _latest_main_revision(worktree_path: str, batch_files: list[str]) -> str | None:
    """Compute main's current head using only the main-only migration chain.

    Copies every .py file under {worktree_path}/orch/db/migrations/versions/
    EXCEPT those listed in batch_files into a fresh TemporaryDirectory, mirrors
    env.py + script.py.mako so Alembic has a complete skeleton, then runs
    ScriptDirectory.from_config(...).get_current_head() against the tmp dir.

    Returns None if the tmp chain is empty. Raises RebaseChainError if the
    tmp chain has > 1 head (pre-existing multi-head on main — not this batch's fault).
    """
    versions_src = Path(worktree_path) / "orch" / "db" / "migrations" / "versions"
    migrations_src = Path(worktree_path) / "orch" / "db" / "migrations"

    with tempfile.TemporaryDirectory(prefix="cr21-main-head-") as tmp_dir:
        tmp_versions = Path(tmp_dir) / "migrations" / "versions"
        tmp_migrations = Path(tmp_dir) / "migrations"
        tmp_migrations.mkdir(parents=True, exist_ok=True)
        tmp_versions.mkdir(parents=True, exist_ok=True)

        batch_set = {Path(fp).name for fp in batch_files}

        if versions_src.exists():
            for f in versions_src.iterdir():
                if f.suffix == ".py" and f.name not in batch_set:
                    shutil.copy2(f, tmp_versions / f.name)

        for name in ("env.py", "script.py.mako"):
            src = migrations_src / name
            if src.exists():
                shutil.copy2(src, tmp_migrations / name)

        cfg = AlembicConfig()
        cfg.set_main_option("script_location", str(tmp_migrations))

        try:
            script_dir = ScriptDirectory.from_config(cfg)
            heads = script_dir.get_heads()
        except Exception as exc:
            raise RebaseChainError(f"Failed to read alembic script directory: {exc}") from exc

        if len(heads) > 1:
            raise RebaseChainError(
                f"Main already has multiple heads before this batch "
                f"— manual intervention required: {heads}"
            )

        if not heads:
            return None

        return heads[0]


def _rewrite_down_revision(path: str, new_value: str) -> None:
    """Regex-replace the down_revision line in a migration file, preserving style."""
    content = Path(path).read_text(encoding="utf-8")
    pattern = re.compile(r"^(down_revision(?:\s*:\s*[^=]+)?\s*=\s*).+$", re.MULTILINE)

    def replacer(match: re.Match[str]) -> str:
        return f"{match.group(1)}{new_value}"

    new_content, count = pattern.subn(replacer, content, count=1)
    if count == 0:
        raise MigrationParseError(f"Could not find down_revision line to replace in {path}")

    Path(path).write_text(new_content, encoding="utf-8")


def _strip_quotes(s: str) -> str:
    """Strip surrounding single or double quotes from a string."""
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        return s[1:-1]
    return s


def _emit_daemon_event(
    event_type: str,
    metadata: dict[str, Any],
    message: str,
) -> None:
    """Write a DaemonEvent row via a fresh short-lived session."""
    if _is_test_context_active():
        return
    db_url = get_db_url()
    engine = safe_create_engine(db_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine)
    session: Session = session_factory()
    try:
        event = DaemonEvent(
            project_id=None,
            event_type=event_type,
            entity_id=None,
            entity_type=None,
            message=message,
            event_metadata=metadata,
        )
        session.add(event)
        session.commit()
    except Exception as exc:
        logger.warning("[rebase] Failed to write daemon event: %s", exc)
        session.rollback()
    finally:
        session.close()
        engine.dispose()


def _write_rebase_log(
    revision: str,
    old_revision: str,
    batch_id: str | int,
) -> None:
    """Write a PendingMigrationLog row for a rebase-phase rewrite."""
    if _is_test_context_active():
        return
    db_url = get_db_url()
    engine = safe_create_engine(db_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine)
    session: Session = session_factory()
    now = datetime.now(UTC)
    try:
        entry = PendingMigrationLog(
            revision=revision,
            old_revision=old_revision,
            direction="upgrade",
            phase="rebase",
            batch_id=batch_id,
            started_at=now,
            completed_at=now,
            success=True,
            stdout_tail="",
            stderr_tail="",
            error_message=None,
        )
        session.add(entry)
        session.commit()
    except Exception as exc:
        logger.warning("[rebase] Failed to write pending_migration_log entry: %s", exc)
        session.rollback()
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_pre_merge_rebase(
    batch_id: str | int,
    worktree_path: str,
    _repo_root: str,
) -> RebaseResult:
    """Rebase the batch's branch onto main and rewrite stale down_revisions.

    Runs inside merge_queue._merge_item's serial critical section, before the
    3-phase migration pipeline (dry_run / apply / rollback).

    ORCH-DB PROJECT ONLY. This rewrites the batch chain root's down_revision onto
    the orch main head and scans the hard-coded ``orch/db/migrations/versions/``
    layout, so it is meaningful only for the project that owns the orch DB
    (iw-ai-core). The merge queue gates the call on
    ``safe_migrate.manages_orch_db(project_id)``; other projects author their own
    migration chains and must never have them rewritten here (I-00131).

    Returns RebaseResult with success=False on fatal errors (git failure,
    parse error, chain cycle). Exceptions must NOT propagate to merge_queue.
    """
    logger.info("[rebase] Starting pre-merge rebase for batch %s", batch_id)

    try:
        # Step 1: Preflight SHAs
        _git(worktree_path, ["fetch", "origin", "main"])
        current_main_sha = _git(worktree_path, ["rev-parse", "origin/main"])
        worktree_base_sha = _git(worktree_path, ["merge-base", "HEAD", "origin/main"])

        rebase_needed = worktree_base_sha != current_main_sha

        # Step 2: Emit preflight DaemonEvent
        _emit_daemon_event(
            event_type="migration_rebase",
            metadata={
                "batch_id": batch_id,
                "worktree_base_sha": worktree_base_sha,
                "current_main_sha": current_main_sha,
                "rebase_needed": rebase_needed,
            },
            message="Pre-merge rebase starting",
        )

        # Step 2b: Early-skip when this batch added no migration files.
        # The rebase exists *only* to rewrite stale down_revisions on migrations
        # this batch added; if there are none, the rebase is a no-op and would
        # only risk failing on unrelated reasons (e.g. unstaged agent work that
        # worktree_commit.sh is responsible for committing). Use origin/main..HEAD
        # which is well-defined regardless of any local 'main' divergence.
        try:
            preflight_added = _git(
                worktree_path,
                [
                    "diff",
                    "origin/main..HEAD",
                    "--name-only",
                    "--diff-filter=A",
                    "--",
                    "orch/db/migrations/versions/",
                ],
            )
        except GitCommandError as exc:
            return RebaseResult(
                success=False,
                rebased=False,
                rewrites=[],
                worktree_base_sha=worktree_base_sha,
                current_main_sha=current_main_sha,
                message="Failed to inspect batch migration files",
                error_message=("git diff origin/main..HEAD failed:\n" + exc.diagnostic_block()),
            )

        preflight_batch_files = [f for f in preflight_added.splitlines() if f.strip()]
        if not preflight_batch_files:
            logger.info(
                "[rebase] Batch added no migration files — skipping rebase (idempotent no-op)"
            )
            return RebaseResult(
                success=True,
                rebased=False,
                rewrites=[],
                worktree_base_sha=worktree_base_sha,
                current_main_sha=current_main_sha,
                message="No migration files added by this batch",
                error_message=None,
            )

        rebased = False

        # Step 3: Run the rebase (no-op if already on main)
        if rebase_needed:
            try:
                _git(worktree_path, ["rebase", "main"])
                rebased = True
            except GitCommandError as exc:
                # Capture worktree state BEFORE the abort so we surface the real
                # cause even when git can't be inspected later.
                state = _capture_worktree_state(worktree_path)
                # Try to abort cleanly, but never let abort failure mask the
                # original rebase error (the abort can fail e.g. when git
                # short-circuited before starting the rebase: "fatal: No rebase
                # in progress?").
                abort_failure: str | None = None
                try:
                    _git(worktree_path, ["rebase", "--abort"])
                except GitCommandError as abort_exc:
                    abort_failure = str(abort_exc)
                    logger.info(
                        "[rebase] git rebase --abort failed (likely no rebase started): %s",
                        abort_exc,
                    )
                detail = exc.diagnostic_block()
                lines = [
                    "git rebase main failed",
                    detail,
                    f"branch: {state.get('branch')}",
                    f"head_sha: {state.get('head_sha')}",
                    f"origin/main: {state.get('origin_main_sha')}",
                    f"working tree dirty: {state.get('dirty')}",
                ]
                if state.get("status_porcelain"):
                    lines.append("--- git status --porcelain ---")
                    lines.append(state["status_porcelain"])
                if abort_failure:
                    lines.append(f"(abort cleanup also failed: {abort_failure})")
                return RebaseResult(
                    success=False,
                    rebased=False,
                    rewrites=[],
                    worktree_base_sha=worktree_base_sha,
                    current_main_sha=current_main_sha,
                    message="Rebase failed and aborted",
                    error_message="\n".join(lines),
                )

        # Step 4: Identify batch's own migration files
        # After rebase, the worktree's local 'main' is always a proper ancestor of
        # HEAD. We use the symmetric diff main..HEAD to find only files added by
        # the batch (not files from the old chain that were carried forward).
        diff_output = _git(
            worktree_path,
            [
                "diff",
                "main..HEAD",
                "--name-only",
                "--diff-filter=A",
                "--",
                "orch/db/migrations/versions/",
            ],
        )
        batch_files = [f for f in diff_output.splitlines() if f.strip()]
        if not batch_files:
            logger.info("[rebase] No batch migration files found — idempotent no-op")
            return RebaseResult(
                success=True,
                rebased=rebased,
                rewrites=[],
                worktree_base_sha=worktree_base_sha,
                current_main_sha=current_main_sha,
                message="No migration files added by this batch",
                error_message=None,
            )

        # Step 5: Parse each added file
        parsed: list[tuple[str, str | None, str]] = []
        for fp in batch_files:
            full_path = Path(worktree_path) / fp
            try:
                revision, down_revision = _parse_migration(str(full_path))
                parsed.append((revision, down_revision, fp))
            except MigrationParseError as exc:
                return RebaseResult(
                    success=False,
                    rebased=rebased,
                    rewrites=[],
                    worktree_base_sha=worktree_base_sha,
                    current_main_sha=current_main_sha,
                    message=f"Parse error in {fp}",
                    error_message=str(exc),
                )

        # Step 6: Order batch files by dependency (find chain root)
        # The file whose down_revision points to a revision NOT in this batch's
        # revision set (or is None) is the chain root. Any cycles / multiple roots → error.
        batch_revisions = {revision for revision, _, _ in parsed}

        roots = [
            (revision, down_revision, fp)
            for revision, down_revision, fp in parsed
            if down_revision is None or down_revision not in batch_revisions
        ]

        if len(roots) != 1:
            return RebaseResult(
                success=False,
                rebased=rebased,
                rewrites=[],
                worktree_base_sha=worktree_base_sha,
                current_main_sha=current_main_sha,
                message="Batch migration graph is not a single chain",
                error_message=(
                    f"Multiple roots detected ({len(roots)}) or cycle detected — "
                    "batch migrations must form a linear chain"
                ),
            )

        # Build ordered chain: root first, then each file pointing to the previous
        chain: list[tuple[str, str | None, str]] = []
        chain_revisions: set[str] = set()
        current = roots[0]
        while True:
            chain.append(current)
            chain_revisions.add(current[0])
            # Find the next file whose down_revision == current.revision
            next_file = None
            for revision, down_revision, fp in parsed:
                if down_revision == current[0] and revision not in chain_revisions:
                    next_file = (revision, down_revision, fp)
                    break
            if next_file is None:
                break
            current = next_file

        # Detect cycles (shouldn't happen given the ordering, but double-check)
        if len(chain) != len(parsed):
            return RebaseResult(
                success=False,
                rebased=rebased,
                rewrites=[],
                worktree_base_sha=worktree_base_sha,
                current_main_sha=current_main_sha,
                message="Batch migration graph has a cycle",
                error_message="Migration files form a cycle instead of a linear chain",
            )

        # Step 7: Determine expected down_revision for each file
        # Chain root → main's current head (via _latest_main_revision)
        try:
            main_head = _latest_main_revision(worktree_path, batch_files)
        except RebaseChainError as exc:
            return RebaseResult(
                success=False,
                rebased=rebased,
                rewrites=[],
                worktree_base_sha=worktree_base_sha,
                current_main_sha=current_main_sha,
                message="Main migration chain error",
                error_message=str(exc),
            )

        root_expected = main_head  # None if main has no migrations (brand-new repo)

        expected_down: dict[str, str | None] = {}
        for i, (revision, _down_revision, _fp) in enumerate(chain):
            if i == 0:
                expected_down[revision] = root_expected
            else:
                expected_down[revision] = chain[i - 1][0]

        # Step 8: Rewrite stale files
        rewrites: list[Rewrite] = []
        rewritten_paths: list[str] = []

        for revision, _down_revision, _fp in chain:
            expected = expected_down[revision]
            # "PENDING" is the canonical sentinel for late-bound migrations (CR-00091).
            # It is never equal to any real revision ID, so it always triggers a rewrite
            # here. No special-casing needed — the condition handles it correctly.
            if _down_revision == expected:
                continue

            old_down = _down_revision if _down_revision is not None else "None"
            new_down = expected if expected is not None else "None"

            _rewrite_down_revision(
                str(Path(worktree_path) / _fp),
                f'"{new_down}"' if new_down != "None" else "None",
            )
            rewrites.append(
                Rewrite(
                    revision=revision,
                    old_down_revision=old_down,
                    new_down_revision=new_down,
                )
            )
            rewritten_paths.append(_fp)

        # Step 9: Commit rewrites
        if rewrites:
            try:
                _git(worktree_path, ["add", *rewritten_paths])
                _git(
                    worktree_path,
                    [
                        "commit",
                        "--no-verify",
                        "-m",
                        "chore(migration-rebase): rewrite down_revision for "
                        + ", ".join(r.revision for r in rewrites),
                    ],
                )
            except GitCommandError as exc:
                return RebaseResult(
                    success=False,
                    rebased=rebased,
                    rewrites=rewrites,
                    worktree_base_sha=worktree_base_sha,
                    current_main_sha=current_main_sha,
                    message="Rewrite commit failed",
                    error_message="rewrite commit failed:\n" + exc.diagnostic_block(),
                )

        # Step 10: Write PendingMigrationLog rows
        for rewrite in rewrites:
            _write_rebase_log(
                revision=rewrite.revision,
                old_revision=rewrite.old_down_revision,
                batch_id=batch_id,
            )

        # Step 11: Return success
        msg = f"Rebase complete: {len(rewrites)} rewrite(s)"
        logger.info("[rebase] %s", msg)
        return RebaseResult(
            success=True,
            rebased=rebased,
            rewrites=rewrites,
            worktree_base_sha=worktree_base_sha,
            current_main_sha=current_main_sha,
            message=msg,
            error_message=None,
        )

    except GitCommandError as exc:
        logger.exception("[rebase] Git command failed for batch %s", batch_id)
        return RebaseResult(
            success=False,
            rebased=False,
            rewrites=[],
            worktree_base_sha=None,
            current_main_sha=None,
            message="Git command failed",
            error_message=exc.diagnostic_block(),
        )

    except Exception as exc:
        logger.exception("[rebase] Unexpected error for batch %s", batch_id)
        return RebaseResult(
            success=False,
            rebased=False,
            rewrites=[],
            worktree_base_sha=None,
            current_main_sha=None,
            message="Unexpected error",
            error_message=str(exc),
        )
