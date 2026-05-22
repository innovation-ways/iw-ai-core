# CR-00078_S11_CodeReview_prompt

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S11
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
This step is review-only.

## Scope of Review

Per-agent review of S10's tests against the iw-ai-core-testing red-flag checklist.

1. **Assertion strength** — every test uses exact-value comparisons (`==` on full lists/tuples, exact `event_type` strings, exact row counts). No `assert result`, `assert response.ok`, `assert len(rows) > 0`.
2. **`pytest.raises(IntegrityError)` (not bare Exception)** — verify the composite-PK uniqueness test uses the precise exception class.
3. **Idempotency case asserts row COUNT, not boolean** — `test_post_ignore_idempotent` queries the row count after two POSTs and asserts `== 1` (single row); also asserts `== 2` for the audit events (audit preserved).
4. **Per-batch isolation (AC5)** — the `test_per_batch_isolation` case actually seeds TWO batches with distinct ids and asserts behaviour for BATCH-B. If it cheats by reusing BATCH-A but asserts on a different held_item_id, that's a CRITICAL false-positive — AC5 is specifically about the same held_item across batches.
5. **Testcontainer only** — `tests/conftest.py:db_session` fixture is used everywhere. No `postgresql://...5433` string in any test file.
6. **TDD RED** — each new file has a paired `tdd_red_evidence`. The evidences look like real failures (`AssertionError`, `IntegrityError`, 404-vs-200 mismatch), not import errors or fixture errors.
7. **No mocking of the DB** in integration tests — direct testcontainer use, per `tests/CLAUDE.md`.
8. **No `xfail` / `skip`** — every new test runs to a pass/fail outcome. If S10 added an xfail, flag MEDIUM with a request to either fix or delete.
9. **Edge cases covered** — the AC1-AC8 matrix has at least one test per AC (S10's report should map this; if it doesn't, ask for the mapping in your review).

## Severity Guide

- CRITICAL: live-DB connection, mock of DB in integration test, AC5 test that doesn't actually test cross-batch isolation, vacuous primary-key assertion.
- HIGH: missing pytest.raises specificity, missing idempotency count assertion, missing AC coverage that can't be salvaged by browser_verification.
- MEDIUM: xfail/skip without justification, slow tests (>5s each in unit), unused fixtures.
- LOW: naming, ordering.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "code-review-impl",
  "work_item": "CR-00078",
  "completion_status": "complete",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "review-only step",
  "tdd_red_evidence": "n/a — review step",
  "blockers": [],
  "notes": "<count of CRITICAL/HIGH/MEDIUM/LOW findings>"
}
```
