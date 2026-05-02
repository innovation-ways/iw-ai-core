# F-00078_S02_CodeReview_Database_prompt

**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state. See full list in S01 prompt.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live DB.
Read-only operations and testcontainer-driven verification are fine.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00078 --json`.
- `ai-dev/active/F-00078/F-00078_Feature_Design.md` -- Design document
- `ai-dev/work/F-00078/reports/F-00078_S01_Database_report.md` -- S01 report
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/work/F-00078/reports/F-00078_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing the database changes done in S01 for **F-00078**.

The S01 step extended `StepType` with a new `self_assess` value and added an Alembic migration. This is a deliberately tiny change — most of the review value is in catching small but expensive mistakes (wrong enum placement, missing autocommit block for `ALTER TYPE`, accidentally running migrations against the live DB).

Read the design document to understand what was intended. Read the implementation report. Then review all changed files.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these on the files listed in the implementation report's `files_changed`:

```bash
make lint          # ruff check
make format-check  # ruff format --check (does NOT auto-fix)
```

If either reports NEW violations in the changed files, classify each as a **CRITICAL** finding with `category: conventions`.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Enum value placement and naming

- Is the new value placed near `browser_verification` (the closest precedent), not at the end of an unrelated cluster?
- Does the value use `self_assess` (snake_case, matching other enum values)?
- Does `StepType.self_assess.value == "self_assess"` exactly?

### 2. Migration correctness

- Does the migration use `ALTER TYPE step_type ADD VALUE 'self_assess'`?
- Does it run OUTSIDE a transaction (autocommit block, `transactional = False`, or whatever the project's pattern is)? Check by looking at the most recent enum-extending migration in `orch/db/migrations/versions/` — the new migration MUST match that pattern.
- Is `down_revision` correctly set to point at the previous migration head?
- Is the `downgrade()` function consistent with the project's convention for irreversible enum extensions (no-op or `raise NotImplementedError`)?

### 3. Did the agent run alembic upgrade against the live DB?

- The S01 report should NOT mention running `alembic upgrade` outside testcontainers. If it does, this is a CRITICAL finding (R2 violation).

### 4. Test coverage

- Was a unit test added for the enum value? Does it actually exercise the new value rather than just import it?
- Did integration tests run against a testcontainer with the migration applied? Check the report.

### 5. Out-of-scope changes

- The S01 step is database-only. Any change to `orch/daemon/`, `dashboard/`, `skills/`, or anywhere outside `orch/db/` and the new migration file is out of scope and should be flagged HIGH so it can be reverted and redone in the right step.

### 6. Project conventions

- Read `orch/CLAUDE.md` for SQLAlchemy 2.0 / Mapped[] patterns (not directly relevant for an enum value, but the surrounding model file should remain consistent).

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make test-unit` — must pass.
2. Run `make test-integration` — must pass with the testcontainer applying the new migration.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Migration won't apply, data loss risk, R1/R2 violation | Must fix |
| **HIGH** | Wrong enum placement, missing autocommit block, out-of-scope changes | Must fix |
| **MEDIUM (fixable)** | Convention drift, unclear test name | Should fix |
| **MEDIUM (suggestion)** | Optional improvement | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00078",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "...",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
