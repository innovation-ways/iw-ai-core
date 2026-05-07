# F-00079_S02_CodeReview_Database_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection allowed. Full policy in `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp`. Read-only inspection only.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00079 --json`
- `ai-dev/active/F-00079/F-00079_Feature_Design.md` — design document
- `ai-dev/active/F-00079/reports/F-00079_S01_Database_report.md` — implementation report
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/active/F-00079/reports/F-00079_S02_CodeReview_report.md`

## Context

You are reviewing the database schema migration and ORM model updates done in S01 for **F-00079: Files view**. Read the design document's `Schema additions` section and the `Invariants` list (especially Invariant 6 about append-only safety on `step_runs`) before reviewing.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any NEW violations in S01's changed files → CRITICAL findings with `category: "conventions"`.

## Review Checklist

### 1. Migration Correctness

- The migration file contains EXACTLY 5 `op.add_column` calls (3 on `work_items`, 2 on `step_runs`).
- All columns are nullable (no `nullable=False`).
- No server defaults set values on existing rows.
- No indexes that would scan existing rows.
- `downgrade()` drops the columns in reverse order.
- Migration message clearly describes the change.
- `down_revision` is set correctly (not None for a non-initial migration; not a stale revision).

### 2. ORM Model Updates

- `WorkItem.diff_text` is `Mapped[str | None]` typed `Text`, nullable, with a clear comment.
- `WorkItem.diff_summary` is `Mapped[Any | None]` typed `JSONB`, nullable, with a clear comment describing the list-of-objects shape.
- `WorkItem.merge_commit_sha` is `Mapped[str | None]` typed `Text`, nullable, with a clear comment.
- `StepRun.diff_text` and `StepRun.diff_summary` follow the same patterns.
- The new columns sit in a logical position within the model class (grouped with related fields, not appended in random order).
- Existing `WorkItem.config` / `WorkItem.impacted_paths` are mirrored as JSONB precedents — the new JSONB column declarations should match the same style.

### 3. Append-Only Safety (Invariant 6)

- The new columns are NULL by default and will be written exactly once during the same transaction that finalises the row (S03's responsibility, not S01's, but check the design document description matches this contract).
- No constraint forces the columns to be populated — capture is best-effort.

### 4. Conventions

- Driver: `psycopg` v3 (psycopg2 is forbidden — should not appear in any new code).
- ORM style: SQLAlchemy 2.0 `Mapped[]` declarative.
- Naming: snake_case columns, no abbreviations beyond `sha` (which is well-known).
- Comments: descriptive enough that a reader unfamiliar with F-00079 can understand the column's purpose.

### 5. Test Verification

- `make test-unit` passes.
- No regression in existing tests.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

Run before submitting the review.

## Severity Levels

| Severity | Meaning | Action Required |
|---|---|---|
| CRITICAL | Breaks functionality, data loss risk, security | Must fix before merge |
| HIGH | Significant bug, missing requirement, architectural violation | Must fix before merge |
| MEDIUM (fixable) | Code quality, missing edge case, convention violation | Should fix in fix cycle |
| MEDIUM (suggestion) | Design improvement, better pattern available | Optional |
| LOW | Nitpick, style preference | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "F-00079",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
