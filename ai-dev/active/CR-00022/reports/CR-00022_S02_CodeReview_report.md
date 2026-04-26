# CR-00022_S02 Code Review Report

**Work Item**: CR-00022 — OSS Compliance redesign
**Step Reviewed**: S01 (database-impl)
**Review Step**: S02
**Agent**: code-review-impl
**Files Reviewed**:
- `orch/db/migrations/versions/c062b6bf5eb3_cr_00022_oss_redesign_drop_prepare_.py`
- `orch/db/models.py`
- `docs/IW_AI_Core_Database_Schema.md`

---

## Verdict: **approve**

All checklist items pass. No changes required.

---

## 1. Migration Correctness — ✅ PASS

| Check | Status | Evidence |
|-------|--------|----------|
| Pre-delete order (rows deleted before enum recreate) | ✅ | Lines 25-27 delete rows before any column/enum DDL |
| Pre-delete for `oss_scan.mode IN ('make_oss','publish')` | ✅ | Line 26 |
| Pre-delete for `project_oss_job.status IN ('awaiting_review','discarded')` (defensive) | ✅ | Line 27 |
| Enum recreate uses create-new → alter-cast → drop-old → rename pattern | ✅ | Lines 42-48, 51-57, 60-69 — no `DROP VALUE` |
| `fix` added to `project_oss_job_kind` enum | ✅ | Line 42 creates `('scan','install','fix')` |
| All four columns dropped from `project_oss_job` | ✅ | Lines 30-33: `files_changed_summary`, `commit_sha`, `branch_name`, `worktree_path` |
| `auto_apply_safe BOOLEAN NOT NULL DEFAULT false` added to `oss_finding` | ✅ | Lines 36-39 |
| `down_revision` points at `550aecbbd42b` (current head) | ✅ | `alembic history` confirms: `550aecbbd42b -> c062b6bf5eb3 (head)` |
| `downgrade()` raises `NotImplementedError` | ✅ | Lines 72-75 |

**Finding**: None. Migration is structurally correct.

---

## 2. ORM Consistency — ✅ PASS

| Check | Status | Evidence |
|-------|--------|----------|
| `ProjectOssJobKind` removed `prepare`/`publish`, added `fix` | ✅ | Line 271-274: `scan, install, fix` — no `prepare`/`publish` |
| `OssScanMode` removed `make_oss`/`publish` | ✅ | Lines 239-240: `scan` only |
| `ProjectOssJobStatus` removed `awaiting_review`/`discarded` | ✅ | Lines 277-282: `queued, running, complete, error, cancelled` |
| `ProjectOssJob` model dropped four columns | ✅ | No `worktree_path`, `branch_name`, `commit_sha`, `files_changed_summary` in model (lines 1677-1720) |
| `OssFinding` has `auto_apply_safe: Mapped[bool]` with `server_default=text("false")` | ✅ | Lines 1627-1629 |
| No stale relationships pointing at dropped fields | ✅ | `ProjectOssJob.scan` uses `foreign_keys=[scan_id]` correctly |
| Class docstring updated | ✅ | Line 1678: `"Async OSS scan/install/fix job tracking"` |

**Finding**: None. ORM is consistent with the schema.

---

## 3. Schema Docs — ✅ PASS

Section 10 of `docs/IW_AI_Core_Database_Schema.md` (line 814) documents:
- `project_oss_job_kind` redesign with SQL examples (lines 818-832)
- `ossscan_mode` redesign (lines 834-848)
- `project_oss_job_status` redesign (lines 850-864)
- Column drops table (lines 866-876)
- `auto_apply_safe` column spec (lines 877-883)

CR-00022 is named in the section title. Complete and accurate.

**Finding**: None.

---

## 4. Project Conventions — ✅ PASS

- **Precedent style**: `9ef17911f546_*` adds columns to `project_oss_job`; this migration drops columns from the same table. Style matches.
- **No f-string injection**: All `op.execute(...)` calls use plain string literals with no user-input interpolation.
- **Imports**: `alembic.op`, `sqlalchemy as sa` — correct.

**Finding**: None.

---

## 5. Test Impact — ✅ PASS (noted for S17)

S01 report (line 66) explicitly calls out test files needing updates in S17:
- `tests/integration/test_project_oss_job_migration.py` — drop column assertions need updating
- `tests/integration/test_oss_migration.py` — extend with new schema assertions
- `tests/integration/test_oss_persistence.py` — remove `make_oss`/`publish` mode assertions

S01 did not run an integration test in a testcontainer (the report is a code-only report). This is acceptable since S01's scope was ORM + migration generation; the daemon applies migrations via the merge pipeline which includes a pre-merge dry-run testcontainer. The S01 report correctly defers test updates to S17.

**Finding**: None — concern noted for S17.

---

## Summary

The S01 implementation is clean. All five checklist categories pass. No CRITICAL/HIGH/MEDIUM/LOW issues found.

- Migration uses the correct recreate-cast-drop pattern (no `DROP VALUE`)
- Pre-migration deletes are in the right order before any type alteration
- ORM matches schema after migration
- Docs reflect all changes
- Style follows existing precedent