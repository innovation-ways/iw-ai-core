# F-00079_S02_CodeReview_report.md

## Step: S02 — Code Review (Database Schema + ORM Models)

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Agent**: code-review-impl
**Step Reviewed**: S01 (database-impl)
**Date**: 2026-05-07

---

## What Was Reviewed

S01 added five nullable columns across two existing tables (`work_items` +3, `step_runs` +2) via an Alembic migration, and updated the SQLAlchemy ORM models in `orch/db/models.py`.

### Migration File
- **File**: `orch/db/migrations/versions/1713bc13a11d_add_files_view_diff_columns_to_work_.py`
- **Status**: Already existed and is at HEAD of Alembic history
- **Operations**: 5 `op.add_column` calls — correct order: step_runs first (2 cols), then work_items (3 cols)
- All columns are `nullable=True` with no server defaults
- `downgrade()` drops columns in correct reverse order
- `down_revision` correctly set to `7f1a75bb5c2d` (not None, not stale)
- Clear migration message

### ORM Model Updates
- **`WorkItem`** (`orch/db/models.py`, lines 520–538): 3 new mapped columns
  - `diff_text: Mapped[str | None]` — `Text`, nullable, comment: "Raw unified diff of the squash commit captured at merge time"
  - `diff_summary: Mapped[Any | None]` — `JSONB`, nullable, comment describing list-of-objects shape with keys path, status, added, removed, is_generated, is_binary, old_path
  - `merge_commit_sha: Mapped[str | None]` — `Text`, nullable, comment: "SHA of the squash commit on main; enables lazy git diff for completed items"
  - Positioned logically after `archived_at`, grouped together with `# Files view — aggregate diff` comment
  - Matches existing JSONB column style (`config`, `impacted_paths`) in same model

- **`StepRun`** (`orch/db/models.py`, lines 737–750): 2 new mapped columns
  - `diff_text: Mapped[str | None]` — `Text`, nullable, comment: "Raw unified diff captured at iw step-done from the worktree"
  - `diff_summary: Mapped[Any | None]` — `JSONB`, nullable, comment describing same list-of-objects shape
  - Positioned logically after `report_file`, grouped together with `# Files view — per-step diff` comment
  - Same JSONB declaration pattern as WorkItem

### Invariant 6 (Append-Only Safety) Verification
- The design doc (Invariant 6) specifies: "new diff columns are written exactly once during the same `step-done` transaction that finalises the row."
- The migration adds nullable columns with no constraints — no `NOT NULL`, no defaults
- Capture is best-effort; `step-done` writes the columns during the same transaction that finalises the row (consistent with existing pattern for `status`, `completed_at`, `duration_secs`, `report_file`, `log_content`)
- No retroactive updates of terminal `step_runs` rows are introduced

---

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added 5 mapped columns (3 on WorkItem, 2 on StepRun) with comments |
| `orch/db/migrations/versions/1713bc13a11d_add_files_view_diff_columns_to_work_.py` | Already existed at HEAD; verified clean |

---

## Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✓ PASS — All checks passed |
| `make format` | ✓ PASS — 619 files already formatted |
| `make test-unit` | ✓ PASS — 2648 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings in 57.99s |

---

## Migration Verification

```
$ alembic history --verbose
7f1a75bb5c2d -> 1713bc13a11d (head), add files view diff columns to work_items and step_runs
```

- Migration is importable and Alembic resolves it as HEAD
- `downgrade()` correctly drops columns in reverse order (work_items first, then step_runs)
- No spurious autogenerate diffs detected

---

## Notes

- All five columns are nullable with no server defaults — safe for online migration against the live DB without scanning existing rows
- PostgreSQL TOAST handles compression of `diff_text` automatically
- `diff_summary` JSONB uses `astext_type=sa.Text()` matching the existing pattern for JSONB columns in this codebase
- The S01 agent reported the migration "already existed" — this is correct; the migration was generated in a prior run and is already at HEAD of the Alembic history. No new migration was created by S01.
- No violations of CLAUDE.md conventions found in S01's changed files

---

## Verdict

**PASS** — S01 correctly implemented the database schema additions and ORM model updates as specified in the design document. No issues found.
