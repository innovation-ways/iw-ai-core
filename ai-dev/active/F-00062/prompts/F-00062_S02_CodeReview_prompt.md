# F-00062_S02_CodeReview_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute docker / docker-compose state-changing commands. Read-only `docker ps|inspect|logs` and testcontainers via pytest fixtures are allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You do NOT run `alembic upgrade|downgrade|stamp` against the live orch DB. Read-only `alembic history|current|show` is allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/F-00062/F-00062_Feature_Design.md` — design document
- `ai-dev/active/F-00062/reports/F-00062_S01_Database_report.md` — implementation report
- All files listed in S01's `files_changed` (ORM model, migration, schema doc, model test)

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S02_CodeReview_report.md` — review report

## Context

You are reviewing the S01 schema additions for F-00062: three new nullable columns on `batch_items` (`worktree_db_port`, `worktree_app_port`, `worktree_compose_path`), plus possibly the `setup_failed` `BatchItemStatus` enum value if it didn't already exist.

## Review Checklist

### 1. Schema correctness
- All three columns are nullable (NULL is the legacy-mode signal — see Invariant #6 and AC7)
- Column types match the design: `worktree_db_port` and `worktree_app_port` are integers; `worktree_compose_path` is TEXT
- Column docstrings explain the NULL semantics (legacy fallback)
- Column ordering and style match existing `BatchItem` columns (study `worktree_path` for the precedent)

### 2. Migration shape
- Migration is purely additive: only `op.add_column(...)` statements (and possibly the `ALTER TYPE` for `setup_failed`)
- If `ALTER TYPE batch_item_status ADD VALUE 'setup_failed'` is present, it runs INSIDE `op.get_context().autocommit_block()` or as a separate split migration — must NOT run inside a transaction (Postgres mechanics; CR-00019/CR-00021 precedent)
- `downgrade()` drops the three columns; documents that the enum value cannot be removed (Postgres limitation)
- Migration module docstring references F-00062 and explains intent

### 3. ORM/Python consistency
- If `setup_failed` was added to the PG enum, the Python `BatchItemStatus` enum has the matching member
- `Mapped[int | None]` and `Mapped[str | None]` typing matches the nullable columns

### 4. Documentation
- `docs/IW_AI_Core_Database_Schema.md` has the three new column rows with descriptions matching the `comment=` strings
- If `setup_failed` was added, the `batch_item_status` enum section reflects it

### 5. Tests
- Unit test asserts the three columns are present, nullable, and have correct types
- Unit test asserts default-None behavior on construction
- Tests pass cleanly via `make test-unit`

### 6. Project conventions
- Read `CLAUDE.md` and `orch/CLAUDE.md` for ORM/SQLAlchemy patterns
- No `psycopg2` (must be psycopg v3)
- No async (daemon is sync)

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` — verify no regressions
2. Run `make lint` and `make quality`
3. Read the migration file end-to-end and trace the upgrade/downgrade SQL mentally

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Breaks data integrity, schema-incompatible with live orch DB |
| HIGH | Wrong column type, missing nullable, ALTER TYPE inside transaction |
| MEDIUM_FIXABLE | Convention violation, missing comment, missing test |
| MEDIUM_SUGGESTION | Better column ordering, clearer docstring |
| LOW | Style nit |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00062",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "schema|migration|orm|documentation|testing|conventions",
      "file": "path/to/file",
      "line": 42,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
