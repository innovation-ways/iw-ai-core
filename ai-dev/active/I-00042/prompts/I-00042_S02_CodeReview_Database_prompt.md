# I-00042_S02_CodeReview_Database_prompt

**Work Item**: I-00042 — PostgreSQL `batch_item_status` enum missing `migration_invalid` and `migration_rolled_back` labels
**Step Being Reviewed**: S01 (Database)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers spun up by pytest fixtures, read-only `docker ps | inspect | logs`,
and invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orchestration DB
(port 5433). Read-only inspection is fine: `alembic history | current | show`,
`uv run iw migrations list-pending`, `uv run iw migrations dry-run`.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00042/I-00042_Issue_Design.md` — Design document
- `ai-dev/active/I-00042/reports/I-00042_S01_Database_report.md` — S01 step report
- The migration file listed in S01's `files_changed`
- `orch/db/migrations/versions/40af3b76e1d5_cr_00021_rebase_pipeline_phase.py` — Reference migration (canonical pattern)
- `orch/db/models.py` (lines 139–160) — Python `BatchItemStatus` enum

## Output Files

- `ai-dev/active/I-00042/reports/I-00042_S02_CodeReview_Database_report.md` — Review report

## Context

S01 wrote a migration that adds `migration_invalid` and `migration_rolled_back` to
the PostgreSQL `batch_item_status` enum. Your job is to verify the migration is
correct, idempotent, and reversibility-documented.

## Review Checklist

### 1. Correctness

- Does `upgrade()` add both `migration_invalid` AND `migration_rolled_back`? (Missing one is CRITICAL.)
- Is each `ALTER TYPE` inside `op.get_context().autocommit_block()`? PostgreSQL forbids
  the statement inside the implicit alembic transaction; if it's outside the autocommit
  block, the migration will fail at apply time.
- Is `IF NOT EXISTS` used on each ADD VALUE? (Idempotency.)
- Does `down_revision` chain off `c062b6bf5eb3`? Run `uv run alembic history | head` to
  confirm the chain is linear with no branches.
- Are the literal label strings spelled exactly `'migration_invalid'` and
  `'migration_rolled_back'` — matching the Python enum values in `orch/db/models.py:151-152`?
  (A typo here is a CRITICAL silent bug — the migration would succeed but the daemon
  would still crash because the labels still don't match.)

### 2. Reversibility

- Does `downgrade()` exist and is it documented as a no-op? (PostgreSQL cannot drop
  enum labels without rebuilding the type.)
- Is the no-op comment explicit about why? (Match CR-00021's wording.)

### 3. Style and conventions

- Is `from __future__ import annotations` present?
- Are type annotations PEP 604 (`X | Y`)?
- Does the docstring follow the `40af3b76e1d5` template (one-line summary, numbered
  deltas, "Reversibility" section)?
- Does `make lint` pass on the new file?

### 4. Scope

- Does the migration ONLY touch the enum? Any other DDL change is OUT OF SCOPE for
  this incident — flag as CRITICAL.
- Are there any unintended changes to `orch/db/models.py`, daemon code, or other
  files? (S01 instructions explicitly forbid this.)

### 5. Testing (verification, not test authoring)

S03 writes the regression test. For your review:

- Run `uv run iw migrations dry-run` against a fresh testcontainer and confirm the
  migration applies cleanly and is listed in the output.
- After the dry-run, query the testcontainer's `pg_enum` to confirm both labels are
  present. (Use `tests/integration/conftest.py`-style fixture access if needed, or
  craft a one-shot script.)

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. `uv run iw migrations dry-run` — must succeed.
2. `make lint` — must pass.
3. `make test-unit` — must pass with zero failures.

If any fail, this is a finding (CRITICAL if dry-run fails; HIGH otherwise).

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Migration won't apply, wrong/missing label, scope violation, dry-run fails | Must fix before merge |
| **HIGH** | Wrong down_revision chain, missing autocommit_block, lint fails | Must fix before merge |
| **MEDIUM (fixable)** | Docstring deviates from canonical pattern, style nit on type annotations | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better naming, additional defensive check | Optional |
| **LOW** | Stylistic preference | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00042",
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
  "test_summary": "dry-run succeeded; lint clean; X unit passed, 0 failed",
  "notes": ""
}
```

`verdict: pass` requires zero CRITICAL, zero HIGH, AND zero MEDIUM (fixable) findings.
