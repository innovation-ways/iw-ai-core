# F-00079_S01_Database_report.md

## Step: S01 — Database Schema Migration

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Agent**: database-impl
**Date**: 2026-05-07

---

## What Was Done

Reviewed the design document (`F-00079_Feature_Design.md`) and confirmed that the schema additions described in the `Schema additions` section were already implemented in a prior run (migration `1713bc13a11d` is at HEAD of the Alembic history).

### Migration File

- **File**: `orch/db/migrations/versions/1713bc13a11d_add_files_view_diff_columns_to_work_.py`
- **Status**: Already exists and is at HEAD
- **Operations**: 5 `ADD COLUMN` (3 on `work_items`, 2 on `step_runs`), with corresponding `DOWNLOAD` in `downgrade()`:
  - `work_items.diff_text` (TEXT, NULL)
  - `work_items.diff_summary` (JSONB, NULL)
  - `work_items.merge_commit_sha` (TEXT, NULL)
  - `step_runs.diff_text` (TEXT, NULL)
  - `step_runs.diff_summary` (JSONB, NULL)

### ORM Model Updates

- **`WorkItem`** (`orch/db/models.py`, lines 520–538): Three new columns already present:
  - `diff_text: Mapped[str | None]` — Raw unified diff of the squash commit captured at merge time
  - `diff_summary: Mapped[Any | None]` — JSONB parsed file metadata
  - `merge_commit_sha: Mapped[str | None]` — SHA of the squash commit on `main`

- **`StepRun`** (`orch/db/models.py`, lines 737–750): Two new columns already present:
  - `diff_text: Mapped[str | None]` — Raw unified diff captured at `iw step-done`
  - `diff_summary: Mapped[Any | None]` — JSONB parsed file metadata

Both declarations match the existing JSONB column style (e.g., `WorkItem.config`, `WorkItem.impacted_paths`).

---

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Already contained the 5 new mapped columns; confirmed at lines 520–538 (WorkItem) and 737–750 (StepRun) |
| `orch/db/migrations/versions/1713bc13a11d_add_files_view_diff_columns_to_work_.py` | Already existed at HEAD; migration applies cleanly |

---

## Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✓ OK — 619 files already formatted |
| `make typecheck` | ✓ OK — 0 errors in 228 source files |
| `make lint` | ✓ OK — All checks passed |
| `make test-unit` | ✓ OK — 2648 passed, 4 skipped, 5 xfailed, 1 xpassed |

---

## Migration Verification

```
$ alembic history --verbose
7f1a75bb5c2d -> 1713bc13a11d (head), add files view diff columns to work_items and step_runs
```

The migration is importable and Alembic resolves it as HEAD. The `downgrade()` function correctly drops columns in reverse order (step_runs first, then work_items).

---

## Notes

- All five columns are nullable with no server defaults — safe for online migration against the live DB without scanning existing rows.
- The `step_runs.diff_text` and `diff_summary` columns are written during the same `step-done` transaction that finalises the row (consistent with the existing append-only pattern for in-flight field updates).
- No schema doc update was needed — the ORM model serves as the source of truth.
- No spurious autogenerate diffs were detected; the migration file is clean.
