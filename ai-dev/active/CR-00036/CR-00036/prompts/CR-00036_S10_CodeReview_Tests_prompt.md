# CR-00036_S10_CodeReview_prompt

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
**Step Being Reviewed**: S09 (tests-impl)
**Review Step**: S10

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- `ai-dev/work/CR-00036/reports/CR-00036_S09_Tests_report.md`
- All test files listed in S09's `files_changed`.

## Output Files

- `ai-dev/work/CR-00036/reports/CR-00036_S10_CodeReview_report.md`

## Context

You are reviewing the additional test coverage for CR-00036. The earlier impl steps already wrote minimal RED-then-GREEN tests; S09 added cross-cutting and end-to-end coverage.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations → CRITICAL findings under `category: conventions`.

## Review Checklist

### 1. AC coverage

- Read S09's "AC coverage matrix" in its report.
- For each AC1..AC10, AC11a, AC11b, confirm the cited test actually exercises the documented Given/When/Then. Stub or trivial tests that only assert `True is True` are CRITICAL findings.
- Any AC marked "covered by impl-step test" must be verified — find the impl test and assert it actually covers the AC.

### 2. Real behaviour, not mocks

- The merge-queue gate test (`test_merge_queue_auto_merge_gate.py`) MUST exercise real ORM transitions and the real `process_merge_queue` function. Mocking the function being tested is a CRITICAL finding.
- Mocking the executor script (`worktree_commit.sh`) is acceptable — that's the project convention for merge tests.

### 3. Testcontainer hygiene

- No live-DB connections (port 5433). Tests use the `db_session` fixture or testcontainer setup.
- After `create_all()`, FTS DDL is bootstrapped (CRITICAL if missing).
- psycopg2 URL is replaced with psycopg.

### 4. Determinism

- No `time.sleep` or wall-clock assumptions.
- No reliance on iteration order of unsorted collections.
- Tests pass in isolation AND in the suite (run `pytest tests/integration/test_merge_queue_auto_merge_gate.py -v` to spot-check).

### 5. Coverage gaps

- Failed-item bypass scenario (AC10) — verify it's not just "no Merge button rendered" but actually checks the `BatchItem.status` never enters `awaiting_merge_approval`.
- Plan-tab toggle disable rule (AC11a/AC11b) — covers BOTH the editable-status set and the disabled-status set.
- Approve-merge rejection — covers `merging`, `merged`, `failed`, etc., not just one wrong status.

### 6. Enum iteration

- `awaiting_merge_approval` appears in any `BatchItemStatus`-iterating tests. Missing the new value is a HIGH finding because the gap will silently grow as the project expands.

## Test Verification (NON-NEGOTIABLE)

Run the full test suite (`make test-unit`, `make test-integration`, `make test-dashboard`). All must pass.

## Severity Levels

| Severity | Examples |
|----------|----------|
| CRITICAL | AC has no real test (only stub); test mocks the function under test; live-DB connection |
| HIGH | Missing enum-iteration update; missing rejection-status coverage; flaky timing |
| MEDIUM (fixable) | Weak assertion message, missing parametrize, redundant setup |
| LOW | Nitpick |

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "CodeReview",
  "work_item": "CR-00036",
  "step_reviewed": "S09",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
