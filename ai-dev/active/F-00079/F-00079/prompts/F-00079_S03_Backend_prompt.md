# F-00079_S03_Backend_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. Allowed: testcontainers in pytest fixtures, read-only docker introspection, `./ai-core.sh`/`make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. The migration was added in S01 and is applied by the daemon.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00079 --json`
- `ai-dev/active/F-00079/F-00079_Feature_Design.md`
- `ai-dev/active/F-00079/reports/F-00079_S01_Database_report.md` and `..._S02_CodeReview_report.md`
- `orch/cli/step_commands.py:277-460` — current `step-done` implementation; insertion point at line 389 where `_worktree_path` is captured
- `orch/daemon/merge_queue.py` — current squash-merge orchestration
- `executor/worktree_commit.sh:434` — the actual `git merge --squash` (shell, do NOT modify)
- `orch/db/models.py` — `WorkItem` (line 406), `StepRun` (line 656), `DaemonEvent` (for warning emission pattern)
- `pyproject.toml` — dependency declaration

## Output Files

- New: `orch/diff_service.py`
- Modified: `orch/cli/step_commands.py`, `orch/daemon/merge_queue.py`, `pyproject.toml`, `uv.lock`
- `ai-dev/active/F-00079/reports/F-00079_S03_Backend_report.md`

## Context

You are implementing the backend services for **F-00079: Files view** — the diff source resolver, the per-step capture in `iw step-done`, and the aggregate capture in the daemon's merge queue. Read the design document's `Functional Requirements`, `Boundary Behavior`, and `Invariants` sections in full. Pay special attention to Invariants 4, 5, 6, 7 (best-effort capture, append-only safety, None-on-empty resolver).

## Requirements

### 1. Add `unidiff` dependency

Add `unidiff>=0.7,<1` to `pyproject.toml` under the standard dependencies block. Run `uv lock` to update `uv.lock`. The package is MIT licensed, stable, and used to parse unified diff text into structured `PatchSet`/`PatchedFile`/`Hunk`/`Line` objects.

### 2. Create `orch/diff_service.py`

A new module exposing the diff resolver and parser. Public API (suggested names; match conventions you see in similar `orch/` modules):

```python
GENERATED_FILE_GLOBS: tuple[str, ...] = (
    "uv.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "poetry.lock", "*.min.js", "*.snap",
)

def resolve_diff(
    *,
    item: WorkItem,
    step_run: StepRun | None,
    project: Project,
    worktree_path: str | None,
) -> str | None:
    """Return the raw unified diff for the given (item, optional step) or None.

    Resolution order:
      step_run provided → step_run.diff_text if present, else live `git diff`
        in worktree against step's commit SHA, else None.
      step_run is None and item.archived_at: → item.diff_text (DB snapshot).
      step_run is None and item.merge_commit_sha: → live
        `git diff <sha>^..<sha>` in project.repo_root.
      step_run is None and worktree alive: → live `git diff <base>...HEAD`
        in worktree.
      Otherwise → None.
    """

def parse_diff_summary(diff_text: str) -> list[dict]:
    """Parse a unified diff into a JSON-serialisable summary list.

    Each entry: {
        "path": str,
        "status": "A" | "M" | "D" | "R",
        "added": int,
        "removed": int,
        "is_generated": bool,
        "is_binary": bool,
        "old_path": str | None,
    }
    """

def is_generated_path(path: str) -> bool:
    """Match path against GENERATED_FILE_GLOBS using fnmatch."""
```

Implementation notes:
- For `git` shell-outs, use `subprocess.run(...)` with `cwd`, capture stdout/stderr, and a sane timeout (e.g., 30 s). On non-zero exit, log a warning via the standard `logging` module and return `None` from the resolver — never raise.
- Use `unidiff.PatchSet` to parse the diff text.
- For renamed files, `unidiff` exposes `is_rename` and the `source_file` / `target_file` paths — collapse to a single entry with `status="R"` and `old_path=source`. Honour git's default rename detection (similarity ≥ 50%) — do not pass `--no-renames`.
- Binary files in `unidiff`: `is_binary_file=True` → `is_binary=True`, `added=0`, `removed=0`, `status` whatever `unidiff` reports.
- The generated-file glob list in this module is the **single source of truth** consumed by `parse_diff_summary` and (S06) the frontend. Keep it as one canonical constant — do not duplicate.

### 3. Extend `iw step-done` to capture per-step diff

In `orch/cli/step_commands.py:step_done`, just after the existing block that updates the in-flight `step_run` (around line 389 where `_worktree_path` is captured), add a best-effort diff capture:

```python
if step_run is not None and step_run.worktree_path:
    try:
        diff_text = _capture_step_diff(step_run.worktree_path)
        if diff_text:
            step_run.diff_text = diff_text
            step_run.diff_summary = parse_diff_summary(diff_text)
    except Exception:
        logger.warning("step-done: diff capture failed", exc_info=True)
```

Where `_capture_step_diff` runs `git diff HEAD^..HEAD` in the worktree (returns `None` if the worktree has only one commit or git fails). Live this helper in `orch/diff_service.py` so it's reusable in S09 tests.

**Multi-commit step semantics**: under the daemon's one-commit-per-step convention (`executor/worktree_commit.sh` produces a single commit per step), `HEAD^..HEAD` captures the full step delta. If a step produces multiple commits (rare, but possible if a fix cycle re-runs the same step or the executor pattern changes), this capture returns ONLY the most recent commit's diff — earlier commits in the same step are not included. Document this contract in the helper's docstring so future readers don't assume cumulative-since-prior-step semantics. Switching to `git diff <prev_step_sha>..HEAD` is out of scope for v1; revisit if multi-commit steps become common.

Critical: this capture MUST NOT block `step-done`. If anything fails, log a warning and continue. The transition `step.status = StepStatus.completed` must succeed regardless of diff capture state. Existing CLI exit codes and observable side effects must not change on capture failure.

### 4. Capture aggregate diff in `orch/daemon/merge_queue.py`

After the daemon's squash-merge succeeds (`executor/worktree_commit.sh` exits 0 and the squash commit is on `main`), capture the aggregate diff from `project.repo_root`:

```python
# After the post-merge migration apply succeeds and BEFORE worktree reaping:
try:
    head_sha = _git_rev_parse_head(project.repo_root)  # SHA of the squash commit
    diff_text = _git_diff_against_parent(project.repo_root, head_sha)
    if diff_text:
        item.diff_text = diff_text
        item.diff_summary = parse_diff_summary(diff_text)
        item.merge_commit_sha = head_sha
        session.commit()
except Exception:
    logger.warning("merge_queue: aggregate diff capture failed for %s", item.id, exc_info=True)
    _emit_daemon_event(session, project_id, item_id, "diff_capture_failed", level="warning")
```

Critical: this capture MUST NOT roll back the merge. The merge has already succeeded by this point; failure to capture diff is logged as a `daemon_events` warning (use the existing event-emission pattern in the same file or in `orch/daemon/state_machine.py`) and the daemon proceeds. The merge itself is unaffected.

Locate the right insertion point inside `merge_queue.py` — typically just after the post-merge migration apply succeeds and before any cleanup. If you need to factor out a small helper to keep the merge function readable, do so in `orch/diff_service.py`.

### 5. Logging and observability

- Use the module-level `logger` (existing pattern; `logger = logging.getLogger(__name__)`).
- Failed captures emit a `daemon_events` row with type `diff_capture_failed` and a structured payload (`item_id`, `step_id` if applicable, `error`). Match the existing `daemon_events` emission pattern; do not invent a new shape.
- Do not log full diff text; it can be very large.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`:
- Sync SQLAlchemy 2.0; `with get_session() as session:` pattern.
- `psycopg` v3 driver only.
- CLI commands use Click 8; reuse the existing `output_error` and `validate_step_done_transition` helpers.
- Module-level `logger = logging.getLogger(__name__)` — never `print` inside library code.
- Subprocess: pass arguments as a list, not a shell string; never use `shell=True`.

Match existing code patterns (e.g., the way `merge_queue.py` and `migration_pipeline.py` already invoke git commands and emit events).

## TDD Requirement

Follow Red-Green-Refactor:

1. **RED**: Write failing tests in `tests/unit/test_diff_service.py` (S09 will own the full suite, but smoke tests of the resolver and parser belong here too — keep at least:
   - `parse_diff_summary` on a fixture diff with A/M/D/R + binary + generated → expected summary list
   - `resolve_diff` with each branch (archived, merged-not-archived, in-progress with worktree, step provided) using fakes/mocks for the git shell-out
   - `is_generated_path` tested against the canonical glob list
2. **GREEN**: Implement until tests pass.
3. **REFACTOR**: Clean up.

Do not skip the RED phase.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — must pass with zero failures.
2. The new `unidiff` import must resolve cleanly.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/diff_service.py",
    "orch/cli/step_commands.py",
    "orch/daemon/merge_queue.py",
    "pyproject.toml",
    "uv.lock",
    "tests/unit/test_diff_service.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
