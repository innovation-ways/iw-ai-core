# F-00079_S04_CodeReview_Backend_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection allowed.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp`.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00079 --json`
- `ai-dev/active/F-00079/F-00079_Feature_Design.md`
- `ai-dev/active/F-00079/reports/F-00079_S03_Backend_report.md`
- All files listed in S03's `files_changed`

## Output Files

- `ai-dev/active/F-00079/reports/F-00079_S04_CodeReview_report.md`

## Context

You are reviewing the diff resolver, capture hooks, and unidiff parser added in S03. The most important properties to verify are the **best-effort capture invariants** — capture failure must never block `step-done` or roll back a merge — and the **append-only safety** on `step_runs`.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in S03's changed files → CRITICAL findings (`category: "conventions"`).

## Review Checklist

### 1. Diff Resolver Correctness (`orch/diff_service.py`)

- `resolve_diff` returns `None` (never raises) when no source is available.
- Resolution order matches the design document: step → step_run.diff_text → live worktree → None; aggregate → archived DB → live `git diff` against `merge_commit_sha` → live worktree → None.
- Subprocess invocations: pass args as list, no `shell=True`, sane timeout, captured stderr.
- `parse_diff_summary` handles A / M / D / R / binary / generated correctly.
- `GENERATED_FILE_GLOBS` is a single canonical constant (no duplication).
- Renamed files collapse to a single entry with `status="R"` and `old_path` populated.
- `unidiff.PatchSet` is used (not a hand-rolled parser).

### 2. Per-Step Capture (`orch/cli/step_commands.py`)

- Capture happens AFTER `step_run.status = RunStatus.completed` is set (so transition happens unconditionally).
- Capture is wrapped in `try/except Exception` with `logger.warning(..., exc_info=True)` — broad except is INTENTIONAL here (Invariant 4) but should be commented to that effect.
- `step.status = StepStatus.completed` is unaffected by capture failure.
- CLI exit codes are unchanged on failure.
- The `step_run.worktree_path` is used; no hardcoded path.
- The capture writes to `step_run.diff_text` and `step_run.diff_summary` within the same transaction that finalises the row (Invariant 6 — append-only safety).
- No retroactive update of terminal `step_runs` rows.

### 3. Aggregate Capture (`orch/daemon/merge_queue.py`)

- Capture happens AFTER the squash commit is on `main` and AFTER post-merge migration apply succeeds.
- Capture is wrapped in `try/except` and emits a `daemon_events` warning on failure (Invariant 5).
- A failed capture does NOT roll back the merge.
- A failed capture does NOT delete the worktree before retry is possible (the resolver's lazy `git diff` against `merge_commit_sha` is the retry path — confirm this is documented in S03's report).
- `merge_commit_sha` is captured from `git rev-parse HEAD` (or equivalent) in `project.repo_root`, NOT from the worktree.
- Subprocess hygiene matches S03 expectations.
- The new code blends with existing `merge_queue.py` style; helper functions live in `orch/diff_service.py` if they need reuse.

### 4. unidiff Dependency (`pyproject.toml`, `uv.lock`)

- Pinned with a sane version range (`>=0.7,<1`).
- License is MIT (compatible).
- `uv.lock` regenerated cleanly via `uv lock` (no extraneous churn).
- Import works in unit tests.

### 5. Logging and Observability

- `logger = logging.getLogger(__name__)` at module scope; no `print`.
- No full diff text in logs (can be very large).
- `daemon_events` row emitted on aggregate capture failure with structured payload.

### 6. Conventions

- Read `CLAUDE.md` and `orch/CLAUDE.md`.
- Sync SQLAlchemy session pattern: `with get_session() as session:`.
- `psycopg` v3 (no `psycopg2` references).
- Subprocess args as list; no `shell=True`.

### 7. Test Coverage Smoke

- `tests/unit/test_diff_service.py` exists and exercises the resolver branches and parser shapes.
- The full integration suite is owned by S09; this step needs only the smoke unit coverage.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

## Severity Levels

| Severity | Meaning | Action |
|---|---|---|
| CRITICAL | Breaks invariant (capture blocks step-done / rolls back merge) | Must fix |
| HIGH | Significant bug, missing requirement | Must fix |
| MEDIUM (fixable) | Code quality, missing edge case | Should fix |
| MEDIUM (suggestion) | Better pattern available | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "F-00079",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
