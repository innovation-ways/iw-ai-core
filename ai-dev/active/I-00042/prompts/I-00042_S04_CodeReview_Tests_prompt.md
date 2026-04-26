# I-00042_S04_CodeReview_Tests_prompt

**Work Item**: I-00042 — PostgreSQL `batch_item_status` enum missing `migration_invalid` and `migration_rolled_back` labels
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers spun up by pytest fixtures, read-only `docker ps | inspect | logs`,
and invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orchestration DB.
Read-only inspection is fine.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00042/I-00042_Issue_Design.md` — Design document
- `ai-dev/active/I-00042/reports/I-00042_S03_Tests_report.md` — S03 step report
- `tests/integration/test_batch_item_status_enum_drift.py` — The new test file
- `tests/CLAUDE.md` — Test conventions
- `tests/integration/conftest.py` — Testcontainer fixture
- `orch/db/models.py` (lines 139–160) — Python `BatchItemStatus` enum

## Output Files

- `ai-dev/active/I-00042/reports/I-00042_S04_CodeReview_Tests_report.md` — Review report

## Context

S03 wrote `tests/integration/test_batch_item_status_enum_drift.py`. Your job is to
verify the test correctly proves the bug is fixed AND prevents future drift.

Read the design document and the S03 report first to understand what was intended.
Then read the test file and review against the checklist below.

## Review Checklist

### 1. Semantic correctness (CRITICAL)

This is the most important check. The test MUST verify SPECIFIC VALUES, not shape:

- ✓ **Expected**: `assert "migration_invalid" in pg_labels`
- ✓ **Expected**: `assert "migration_rolled_back" in pg_labels`
- ✓ **Expected**: `assert not (set(BatchItemStatus.values) - pg_labels)`
- ✗ **CRITICAL finding**: `assert pg_labels` (just non-empty)
- ✗ **CRITICAL finding**: `assert len(pg_labels) >= 13` (count only — passes with the wrong 13 labels)
- ✗ **CRITICAL finding**: `assert "batch_item_status" in some_introspection_dict` (proves the type exists, not its labels)

If the test does not check the specific values `migration_invalid` and
`migration_rolled_back` by name, this is a CRITICAL finding — the test would have
passed against the bug.

### 2. Drift direction

The drift check must be **one-directional**: `Python ⊆ PG`. The test must NOT assert
`pg_labels == py_labels`, because PG legitimately has dormant orphan labels from past
CRs (e.g., `awaiting_review`, `discarded` from CR-00019).

If the test asserts strict equality, this is a HIGH finding — the test will fail
spuriously even after the bug is fixed.

### 3. Fixture binding

- The test MUST use the existing `db_engine` (or equivalent) testcontainer fixture
  from `tests/integration/conftest.py`.
- The test MUST NOT call `get_db_url()`, must NOT import `orch.config`, and must NOT
  open connections to port 5433. (Any of these is CRITICAL — see `tests/CLAUDE.md`.)
- The test MUST NOT mock the database (CLAUDE.md hard rule).

### 4. Falsifiability

Mentally (or by experiment) confirm: if you renamed S01's migration file so the
labels are NOT added, would this test FAIL with a clear message?

If the answer is "no" (e.g., the assertion message is generic, or the test would
still pass through some unrelated path), this is a HIGH finding.

### 5. Style and conventions

- Imports at top of file
- PEP 604 type hints (`X | Y`)
- Test name follows project convention (`test_<scenario>_<outcome>`)
- No class-based grouping unless the file already uses that style
- `text("...")` for raw SQL — not f-strings or string concatenation (would be a
  SQL-injection finding even though the test data is internal)

### 6. Scope

The test file must contain ONLY the drift test for `batch_item_status`. Tests for
other enums, other tables, or unrelated functionality are out-of-scope drift —
flag as HIGH or CRITICAL depending on severity.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. `uv run pytest tests/integration/test_batch_item_status_enum_drift.py -v` — must
   pass.
2. `make test-unit` — must pass with zero failures.
3. `make lint` — must pass on the new file.

If any fail, this is a finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Test does not check specific values; test would have passed against the bug; uses live DB | Must fix |
| **HIGH** | Strict-equality drift check; missing fixture binding; test isn't falsifiable | Must fix |
| **MEDIUM (fixable)** | Style/convention deviation; missing assertion message | Should fix |
| **MEDIUM (suggestion)** | Better naming, additional defensive check | Optional |
| **LOW** | Nitpick, formatting | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00042",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "testing|conventions|architecture|security|code_quality",
      "file": "tests/integration/test_batch_item_status_enum_drift.py",
      "line": 42,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "1 integration test passed; X unit passed; lint clean",
  "notes": ""
}
```

`verdict: pass` requires zero CRITICAL, zero HIGH, AND zero MEDIUM (fixable) findings.
