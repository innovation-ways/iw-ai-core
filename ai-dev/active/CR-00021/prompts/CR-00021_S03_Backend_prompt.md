# CR-00021_S03_Backend_prompt

**Work Item**: CR-00021 -- Rebase alembic down_revision at merge time
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Testcontainer fixtures only. No `docker compose up/down/stop/kill/rm`. Read-only `docker ps` / `docker inspect` / `docker logs` are fine. `./ai-core.sh` / `make` are fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. The daemon applies migrations post-merge. `alembic revision --autogenerate` is allowed (file-only). Testcontainers are the only way to exercise apply/rollback in development. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00021/CR-00021_CR_Design.md` — Design (read "Desired Behavior" and "Acceptance Criteria" in full; AC1–AC4 drive this step's behaviour)
- `ai-dev/active/CR-00021/reports/CR-00021_S01_Database_report.md` — S01 step report (schema already deployed)
- `orch/daemon/migration_pipeline.py` — **style reference** for phase-module shape (dataclass + runner function + event emission + log writes)
- `orch/db/safe_migrate.py` — style reference for `PendingMigrationLog` writes (see `_write_migration_log`)
- `orch/db/models.py` — `BatchItemStatus`, `PendingMigrationLog`, `DaemonEvent` (S01 additions already in place)
- `orch/daemon/merge_queue.py` — caller-side context only (S05 wires into it; do NOT modify merge_queue here)
- `executor/worktree_commit.sh` — reference for existing git rebase patterns (same error-handling shape expected)

## Output Files

- `orch/daemon/migration_rebase.py` (new) — the new phase module
- `ai-dev/active/CR-00021/reports/CR-00021_S03_Backend_report.md` — step report

## Context

Create the new `migration_rebase.py` daemon module. This is the PHASE module — it implements the rebase-and-rewrite step that will run inside the merge queue's serial critical section, **before** `run_pre_merge_dry_run`. Wiring into `merge_queue.py` + exposing `worktree_path` to `run_pre_merge_dry_run` is S05's job — do NOT touch other daemon files in this step.

Read the design's "Desired Behavior" section fully. The module shape must mirror `orch/daemon/migration_pipeline.py` (dataclass `PipelineResult` ↔ `RebaseResult`; runner functions emit `DaemonEvent` + `PendingMigrationLog` rows).

## Requirements

### 1. Module skeleton

Create `orch/daemon/migration_rebase.py` with the module docstring:

```python
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
```

Standard imports (`from __future__ import annotations` IS fine on daemon modules — unlike `orch/db/models.py`): `logging`, `re`, `subprocess`, `dataclasses`, `datetime`, `pathlib`, plus SQLAlchemy `create_engine`, `sessionmaker`, `text`, and `orch.config.get_db_url`, `orch.db.models.{DaemonEvent, PendingMigrationLog}`.

### 2. `RebaseResult` dataclass

```python
@dataclass(frozen=True)
class Rewrite:
    revision: str
    old_down_revision: str
    new_down_revision: str

@dataclass(frozen=True)
class RebaseResult:
    success: bool
    rebased: bool                  # True iff `git rebase <effective_ref>` actually replayed commits
    rewrites: list[Rewrite]        # may be empty even when success=True (idempotent no-op)
    worktree_base_sha: str | None  # merge-base at entry (for the preflight event)
    current_main_sha: str | None   # effective ref's tip (origin/main on happy path, local main on fallback)
    effective_ref: str | None      # "origin/main" or "main" — which ref the rebase targeted
    fetch_succeeded: bool          # True iff `git fetch origin main` exited 0
    message: str
    error_message: str | None
```

### 3. Public entry point — `run_pre_merge_rebase`

```python
def run_pre_merge_rebase(
    batch_id: int,
    worktree_path: str,
    repo_root: str,
) -> RebaseResult: ...
```

Behaviour (implement in this exact order):

1. **Resolve the effective main ref** (fetch first, decide target, THEN read SHAs — refs must be internally consistent):
   - `fetch_succeeded = True` by default.
   - Try `_git(worktree_path, ["fetch", "origin", "main"])` inside a try/except on `GitCommandError`. On failure: `fetch_succeeded = False`, log a WARNING (`logger.warning("git fetch origin main failed, falling back to local main: %s", stderr)`), and DO NOT raise — the fallback path is a first-class valid path.
   - Choose `effective_ref = "origin/main" if fetch_succeeded else "main"`.
   - `worktree_base_sha = _git(worktree_path, ["merge-base", "HEAD", effective_ref])`
   - `current_main_sha = _git(worktree_path, ["rev-parse", effective_ref])`

   WHY: using the same ref for merge-base, rev-parse, and the rebase target below keeps the three values internally consistent. Mixing `main` (local) and `origin/main` (remote) would silently produce wrong `down_revision` rewrites whenever the two refs diverge.

2. **Emit the preflight DaemonEvent** (always, regardless of whether rebase is needed or which ref was chosen):
   ```python
   _emit_daemon_event(
       event_type="migration_rebase",
       metadata={
           "batch_id": batch_id,
           "worktree_base_sha": worktree_base_sha,
           "current_main_sha": current_main_sha,
           "effective_ref": effective_ref,          # "origin/main" or "main"
           "fetch_succeeded": fetch_succeeded,
           "rebase_needed": worktree_base_sha != current_main_sha,
       },
       message="Pre-merge rebase starting",
   )
   ```

3. **Run the rebase** (no-op if `worktree_base_sha == current_main_sha`):
   - Try `_git(worktree_path, ["rebase", effective_ref])` — `git rebase origin/main` on the happy path, `git rebase main` on the fallback path.
   - On failure → `_git(worktree_path, ["rebase", "--abort"])` (best-effort; ignore abort failure), return `RebaseResult(success=False, rebased=False, rewrites=[], worktree_base_sha, current_main_sha, effective_ref, fetch_succeeded, message="...", error_message=f"git rebase {effective_ref} failed: <stderr>")`.
   - On success → `rebased = True` iff the merge-base moved (i.e., `worktree_base_sha != current_main_sha`).

4. **Identify the batch's own migration files**:
   - `added = _git(worktree_path, ["diff", f"{current_main_sha}..HEAD", "--name-only", "--diff-filter=A", "--", "orch/db/migrations/versions/"])`
   - Split on newlines, filter empty, these are the paths added by the batch.
   - If none → return `RebaseResult(success=True, rebased=<bool>, rewrites=[], ...)` immediately (populate all the effective-ref fields). Idempotent happy path.

5. **Parse each added file** using `_parse_migration(path)` — returns `(revision, down_revision)`:
   - Regex: `^revision\s*=\s*["']([^"']+)["']` and `^down_revision\s*=\s*([^\s#]+)` (handle `None`, `"..."`, `'...'`).
   - Parse failure → return `RebaseResult(success=False, ...)` with a clear message.

6. **Order the batch's own files by dependency** — the file whose `down_revision` is NOT the `revision` of another file in this batch is the chain root. Any cycles / multiple roots → `RebaseResult(success=False, error_message="Batch migration graph is not a single chain")`.

7. **Determine expected `down_revision` for each file**:
   - Chain root → `_latest_main_revision(worktree_path, batch_files)` where `batch_files` is the list from step 4. **Do NOT run `ScriptDirectory` directly against the post-rebase worktree** — at this point the worktree's `orch/db/migrations/versions/` contains both main's migrations AND the batch's migrations, so the chain has either multiple heads (stale case → `MultipleHeadsError`, the very bug we're fixing) or the batch's own head as single head (already-correct case → self-reference after rewrite). Instead:
     1. Create a temporary directory (`tempfile.mkdtemp(prefix="cr21-main-head-")`) and copy **only** the main-only migration files into it. "Main-only" = every `.py` file in `{worktree_path}/orch/db/migrations/versions/` whose path (relative to the worktree) is NOT in `batch_files`. Do NOT forget to copy `env.py` / `script.py.mako` from `{worktree_path}/orch/db/migrations/` into the tmp dir's parent layout as well — Alembic's `ScriptDirectory` expects the full skeleton. (Hint: mirror the structure as `<tmp>/migrations/versions/*.py` + `<tmp>/migrations/env.py` + `<tmp>/migrations/script.py.mako`, then point `script_location` at `<tmp>/migrations`.)
     2. Build an `AlembicConfig` with `script_location = f"{tmp}/migrations"` and call `ScriptDirectory.from_config(cfg).get_current_head()`.
     3. If > 1 head → `RebaseResult(success=False, error_message="Main already has multiple heads before this batch — manual intervention required")` (pre-existing bad state, not caused by this batch).
     4. If 0 heads (empty main-only chain — possible on a brand-new repo) → treat the chain root's expected `down_revision` as `None`.
     5. Clean up the tmp dir in a `finally` block (or use `tempfile.TemporaryDirectory` as a context manager).
   - Non-root files → the `revision` of the preceding file in the batch's chain (unchanged on disk).

8. **Rewrite if stale**: for each file whose on-disk `down_revision` ≠ expected value:
   - Use `re.sub` on the single line `down_revision = "..."` (or `'...'` or `None`), preserving quote style and trailing whitespace/comments. Match at line start with `^down_revision\s*=\s*.+$` in MULTILINE mode, replace RHS only.
   - Record the `Rewrite(revision, old_down, new_down)` entry.

9. **If any rewrites happened**: stage + commit:
   - `_git(worktree_path, ["add", *rewritten_file_paths])`
   - `_git(worktree_path, ["commit", "--no-verify", "-m", f"chore(migration-rebase): rewrite down_revision for {', '.join(r.revision for r in rewrites)}"])`
   - Failure here is unexpected — return `RebaseResult(success=False, ..., error_message="rewrite commit failed: <stderr>")` without reverting (the `rewrite` edits stay on disk; operator can `git reset --hard`).

10. **Write `PendingMigrationLog` rows** — one per rewrite, with:
    - `revision = rewrite.revision`
    - `direction = "upgrade"`
    - `phase = "rebase"`
    - `batch_id = batch_id`
    - `old_revision = rewrite.old_down_revision`
    - `success = True`
    - `started_at = completed_at = now(UTC)` (instantaneous — this isn't a migration execution)
    - `stdout_tail = ""`, `stderr_tail = ""`, `error_message = None`

    Use the same fresh short-lived session pattern as `safe_migrate._write_migration_log`. Failure to write the log is logged (not raised) — the rebase has already succeeded.

11. **Return `RebaseResult(success=True, rebased=<bool>, rewrites=[...], worktree_base_sha, current_main_sha, message="Rebase complete: N rewrites", error_message=None)`**.

### 4. Internal helpers

All helpers are module-level, prefixed `_`, take primitive args:

- `_git(cwd, args) -> str` — wraps `subprocess.run(["git", *args], cwd=cwd, check=False, capture_output=True, text=True, timeout=60)`. On non-zero exit, raise a module-local `GitCommandError(stderr)`.
- `_parse_migration(path) -> tuple[str, str | None]` — returns `(revision, down_revision)`; `down_revision` is `None` only if the migration's line literally reads `down_revision = None`.
- `_latest_main_revision(worktree_path: str, batch_files: list[str]) -> str | None` — copies every `.py` file under `{worktree_path}/orch/db/migrations/versions/` EXCEPT those listed in `batch_files` into a fresh `tempfile.TemporaryDirectory`, mirrors `env.py` + `script.py.mako` so Alembic has a complete skeleton, then runs `ScriptDirectory.from_config(...).get_current_head()` against the tmp dir. Returns `None` if the tmp chain is empty; raises `RebaseChainError` if the tmp chain has > 1 head (pre-existing multi-head on main — not this batch's fault). Cleans up the tmp dir in all exit paths.
- `_rewrite_down_revision(path, new_value) -> None` — regex replace in-place, preserving file newline / encoding (`Path(path).write_text(new_content, encoding="utf-8")`).
- `_emit_daemon_event(...)`, `_write_rebase_log(...)` — fresh-session writers (mirror `safe_migrate._write_migration_log`).

### 5. Exception classes (module-local)

```python
class GitCommandError(RuntimeError):
    """Raised when a git subprocess returns non-zero."""

class MigrationParseError(RuntimeError):
    """Raised when a batch migration file cannot be parsed."""

class RebaseChainError(RuntimeError):
    """Raised when the batch's own migration files do not form a single chain."""
```

These are **internal** — `run_pre_merge_rebase` catches them and converts to `RebaseResult(success=False, ...)`. They must not propagate to merge_queue.

## Project Conventions

- Daemon modules may use `from __future__ import annotations` (unlike `orch/db/models.py`).
- Sync SQLAlchemy 2.0; `sessionmaker(bind=engine)` + `session.close()` + `engine.dispose()` — mirror `migration_pipeline.py` exactly.
- `subprocess.run(check=False, capture_output=True, text=True, timeout=<N>)`; never `shell=True`; never interpolate untrusted strings. `worktree_path` comes from the daemon's DB state (trusted).
- Timestamps: `datetime.now(UTC)`.
- Comments: only non-obvious WHY comments. No narration of WHAT.
- Logging: `logger = logging.getLogger(__name__)`; INFO for phase start / end; WARNING for recoverable failures; log via `logger.exception(...)` in catch-all blocks that return failure.

## TDD Requirement

Follow Red-Green-Refactor. Write unit tests alongside implementation to validate:

1. Preflight DaemonEvent emitted even when rebase is not needed.
2. Idempotent no-op when `down_revision` already matches main head.
3. Rewrite happens for a single stale migration + commit is created.
4. Multi-file chain preserves internal links.
5. `git rebase` conflict → `--abort` + `success=False`.
6. **Fetch-failure fallback**: when `git fetch origin main` fails (remove the remote in the scratch repo), the phase continues using local `main`; preflight DaemonEvent has `fetch_succeeded=false` and `effective_ref="main"`; rewrites still happen correctly against local `main`'s head.

Full AC coverage is S07's job, but S03 must have enough local tests to trust the implementation before handoff.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all unit tests (including your new ones) pass.
2. `make lint` / `make format` / `make typecheck` — all pass.
3. Report accurately.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00021",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/migration_rebase.py",
    "tests/unit/daemon/test_migration_rebase.py"
  ],
  "tests_passed": true,
  "test_summary": "unit X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
