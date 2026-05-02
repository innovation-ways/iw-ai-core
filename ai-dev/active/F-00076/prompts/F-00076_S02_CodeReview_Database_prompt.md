# F-00076_S02_CodeReview_Database_prompt

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S02
**Agent**: code-review-impl
**Reviewing**: S01 (database-impl)

---

## Input Files

- `ai-dev/active/F-00076/F-00076_Feature_Design.md`
- `ai-dev/active/F-00076/reports/F-00076_S01_Database_report.md`
- All files listed in S01's `files_changed`

## Review Scope

Review S01's output against:

1. **Design contract**:
   - Column `WorkItem.impacted_paths` exists, JSONB, NOT NULL, server default `'[]'`.
   - Comment text references F-00076 and explains the source-of-truth role.
   - No `WorkItem.notes` column was added (warnings live in `config["scope_extraction"]` per design).

2. **Migration correctness**:
   - Single revision, single column added, no incidental schema drift (check the autogenerate output was hand-trimmed).
   - Backfill uses `op.get_bind()` with parameterized SQL (no string interpolation).
   - Backfill imports `extract_affected_files` from `orch.batch_planner`.
   - Backfill skips rows in terminal status (`completed`, `archived`).
   - `downgrade()` drops the column.
   - Revision's `down_revision` points at the previous head.

3. **`pathspec` dependency**:
   - Added to `pyproject.toml` dependencies (not dev-dependencies).
   - `uv.lock` updated.

4. **Tests**:
   - Unit test verifies default `[]`, round-trip, NOT NULL constraint.
   - Integration test runs an actual alembic upgrade against a testcontainer fixture, asserts backfill behavior, and asserts skip-when-completed.
   - Follows `tests/CLAUDE.md` rules (psycopg URL replacement, FTS triggers, no `importlib.reload`).

5. **Conventions** (`orch/CLAUDE.md`):
   - SQLAlchemy 2.0 `Mapped[]` style.
   - JSONB import path correct.
   - No psycopg2 references introduced.

## Severity Levels

- **CRITICAL**: contract broken (e.g., column nullable, FTS trigger touched, backfill loses data).
- **HIGH**: missing test, missing rollback, security/SQLi risk.
- **MEDIUM**: style drift, comment quality, missing edge case.
- **LOW**: nit-level.

## Output

Write `ai-dev/active/F-00076/reports/F-00076_S02_CodeReview_Database_report.md` containing:

- Summary verdict (PASS / NEEDS FIXES).
- List of findings grouped by severity. For each: file:line, problem, recommended fix.
- Re-run `make test-unit` and `make test-integration` to confirm S01's tests still pass; record results.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["ai-dev/active/F-00076/reports/F-00076_S02_CodeReview_Database_report.md"],
  "verdict": "PASS|NEEDS_FIXES",
  "findings_count": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
