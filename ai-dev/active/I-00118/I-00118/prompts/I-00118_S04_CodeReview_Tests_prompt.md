# I-00118_S04_CodeReview_Tests_prompt

**Work Item**: I-00118 -- Pre-existing red QV gate poisons in-flight items
**Step**: S04 — Review of S03 test coverage
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Standard policy (testcontainers + read-only introspection only).

## Input Files

- `ai-dev/active/I-00118/I-00118_Issue_Design.md` (AC1-AC4)
- `ai-dev/active/I-00118/reports/I-00118_S03_Tests_report.md`
- `tests/unit/orch/daemon/test_qv_baseline.py`,
  `tests/integration/daemon/test_baseline_qv_pipeline.py`

## Output Files

- `ai-dev/active/I-00118/reports/I-00118_S04_CodeReview_Tests_report.md`

## Review Bars (CRITICAL → must pass)

1. **Repro targets the bug**: a test would have FAILED before S01 (no
   `parse_assertion_scanner` / no subtraction for `assertions`) and passes after.
2. **Semantic assertions**: tests assert specific suppressed/surfaced keys
   (e.g. `delta.failures == ()`, specific test-name membership) — not shape
   (`len >= 0`, truthiness).
3. **Resolver coverage**: a test asserts `parser_for_gate` returns a callable for
   a previously-unknown gate name (the regression-prevention invariant).
4. **Integration test** uses the real pipeline + testcontainer rules (no live DB,
   psycopg URL replacement, FTS DDL if needed).
5. **No tautology/no-assert/mock-only** patterns (would trip the `assertions`
   gate). No `pytest.raises(Exception)` without `match=`.

If any CRITICAL/HIGH: fail with a reason. Otherwise write the report.
