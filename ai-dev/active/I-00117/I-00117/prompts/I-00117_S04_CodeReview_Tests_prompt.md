# I-00117_S04_CodeReview_Tests_prompt

**Work Item**: I-00117 -- Daemon silently dead-ends a non-fixable, non-retryable failed step
**Step**: S04 — Review of S03 test coverage
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Standard policy (testcontainers + read-only introspection only).

## Input Files

- `ai-dev/active/I-00117/I-00117_Issue_Design.md` (AC1-AC3)
- `ai-dev/active/I-00117/reports/I-00117_S03_Tests_report.md`
- `tests/integration/test_recovery_exhausted_escalation.py`

## Output Files

- `ai-dev/active/I-00117/reports/I-00117_S04_CodeReview_Tests_report.md`

## Review Bars (CRITICAL → must pass)

1. **Reproduction test genuinely targets the bug.** It seeds an `implementation`
   step `failed` with retries exhausted + a non-`SPEC_MISMATCH` reason, drives the
   real failed-step handler, and would have FAILED against the pre-fix code (no
   event, status left `in_progress`/`executing`).
2. **Semantic assertions, not shape.** Asserts the specific event_type
   `step_recovery_exhausted`, the specific terminal statuses (`failed` for both
   work item and batch item), and a metadata field — not merely "an event exists"
   or "len > 0".
3. **SPEC_MISMATCH regression** test asserts the spec-mismatch path is taken AND
   the recovery-exhausted event is NOT emitted (mutual exclusion).
4. **Integration placement + testcontainer rules** honored (no live DB, FTS DDL
   if needed, psycopg URL replacement) per `tests/CLAUDE.md`.
5. **No tautology/no-assert/mock-only** patterns (would trip the `assertions`
   gate). No `pytest.raises(Exception)` without `match=`.

If any CRITICAL/HIGH: fail the step with a reason. Otherwise write the report.
