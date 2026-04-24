# CR-00019_S02_CodeReview_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Same rules as the implementation prompt. No docker mutation commands. Testcontainers + read-only `docker ps/inspect/logs` are allowed.

## ⛔ Migrations: agents generate, daemon applies

No `alembic upgrade/downgrade/stamp` against the live DB. Writing/reviewing migration files is allowed.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md`
- `ai-dev/work/CR-00019/reports/CR-00019_S01_Database_report.md`
- All files listed in the S01 report's `files_changed`

## Output Files

- `ai-dev/work/CR-00019/reports/CR-00019_S02_CodeReview_report.md`

## Context

You are reviewing S01 (database layer) for CR-00019: adding `awaiting_review` / `discarded` values to `project_oss_job_status`, four columns to `project_oss_job`, and a `rationale` column to `oss_finding`.

Read the design document's Impact Analysis / Data Migration section and confirm the implementation matches.

## Review Checklist

### 1. Enum-add-value correctness

- Does the migration use `ALTER TYPE ... ADD VALUE IF NOT EXISTS`?
- Is it wrapped in `autocommit_block()` or using `transactional=False`? (ADD VALUE can't run in a transaction on older PG versions.)
- Is the pattern consistent with prior enum-add migrations in this repo? (Inspect `orch/db/migrations/versions/` for precedents — flag inconsistencies.)
- Is the down-migration **deliberately** a no-op for the enum values (with a comment explaining PG's lack of `DROP VALUE`), rather than silently broken?

### 2. Column additions

- All five new columns nullable? No `server_default`? No backfill needed?
- Column comments present and informative?
- Down-migration drops all five columns in the correct reverse order?
- Model classes updated alongside the migration (`orch/db/models.py`)?

### 3. Model correctness

- New columns use `Mapped[str | None]` (not `Mapped[str]`) since nullable.
- Column order: appended at the end of the class, not inserted in the middle.
- No use of reserved SQLAlchemy names (no raw `metadata` attr on any Base subclass).

### 4. Schema docs

- `docs/IW_AI_Core_Database_Schema.md` reflects new enum values, new columns, and the awaiting-review lifecycle note.

### 5. Tests

- Is there a migration-specific integration test that asserts enum values + columns exist post-migration?
- Does it use a testcontainer (not a live DB)?
- Does `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` still apply cleanly?

### 6. Project conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md`. Confirm:
- `postgresql+psycopg://` used (not psycopg2).
- Testcontainer URL replacement pattern followed.
- No `importlib.reload(orch.config)` — use `monkeypatch.delenv()` instead.
- No live-DB access from tests.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — zero failures.
2. `make lint` — clean.
3. `uv run mypy orch/` — clean.
4. Re-run the S01 migration test yourself — passes.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Migration corrupts DB, or data-loss risk | Must fix |
| **HIGH** | Missing requirement, unreversible mistake, convention violation | Must fix |
| **MEDIUM (fixable)** | Code smell, missing docstring, minor tighten | Should fix |
| **MEDIUM (suggestion)** | Design alternative worth considering | Optional |
| **LOW** | Nit | Informational |

Report findings per the result contract below.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00019",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL / HIGH / MEDIUM (fixable) findings.
