# I-00059_S04_CodeReview_Tests_prompt

**Work Item**: I-00059 -- Doc Generation Job Detail Page Shows No Error Info or Parameters
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00059 --json`
- `ai-dev/active/I-00059/I-00059_Issue_Design.md` — Design document
- `ai-dev/active/I-00059/reports/I-00059_S03_Tests_report.md` — S03 tests report
- All test files listed in the S03 report's `files_changed`

## Output Files

- `ai-dev/active/I-00059/reports/I-00059_S04_CodeReview_Tests_report.md` — Review report

## Context

You are reviewing the tests written in S03 for **I-00059**. The tests cover `JobsAggregator._get_doc_generation`'s `raw` dict fix. Your primary concern is **semantic correctness** — tests that check shape (key presence, non-emptiness) would pass even against the pre-fix stub code and are effectively useless.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Report new violations in changed files as CRITICAL findings.

## Review Checklist

### 1. Semantic correctness (highest priority)

For every `assert` statement in the new tests:

- BAD (CRITICAL finding): `assert "error" in row.raw`
- BAD (CRITICAL finding): `assert row.raw.get("error") is not None`
- BAD (CRITICAL finding): `assert row.raw` (truthy)
- GOOD: `assert row.raw.get("error") == "generation timeout after 15 minutes"`

Every assertion must verify a SPECIFIC value that was explicitly set on the test fixture. No shape-only checks.

### 2. Reproduction test existence and completeness

- Does a test with `test_i00059_` prefix exist that directly reproduces the bug?
- Does it assert `error`, `skill_used`, `duration_seconds`, `doc_id`, `trigger_reason` all with specific values?

### 3. Parity test existence

- Does a parity test exist comparing `get_job` and list-path `raw` dicts for the same job?
- This is the key regression guard — flag its absence as HIGH.

### 4. `lint_warnings` test

- Does a test cover the list-type `lint_warnings` field with a specific list value (not just `[]`)?

### 5. Test isolation

- Tests must use the `db_session` testcontainer fixture — NEVER the live DB at port 5433
- Tests must not depend on pre-existing DB state

### 6. Test naming

- All new tests named `test_i00059_*` for traceability

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration` and verify all new tests pass.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00059",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
