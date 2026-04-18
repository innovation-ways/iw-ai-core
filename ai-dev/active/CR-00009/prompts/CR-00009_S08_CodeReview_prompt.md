# CR-00009_S08_CodeReview_prompt

**Work Item**: CR-00009 — Chat panel context awareness
**Step Being Reviewed**: S07 (tests-impl)
**Review Step**: S08

---

## Input Files

- `ai-dev/active/CR-00009/CR-00009_CR_Design.md`
- `ai-dev/active/CR-00009/reports/CR-00009_S07_Tests_report.md`
- All test files listed in the S07 report

## Output Files

- `ai-dev/active/CR-00009/reports/CR-00009_S08_CodeReview_report.md`

## Context

Review S07's test coverage against the acceptance criteria. Focus on whether the tests are enforcing the *contract*, not just executing code paths.

## Review Checklist

### 1. AC Coverage Map

Build an explicit map in your review report:

| AC | Covered by test(s) | Notes |
|----|--------------------|-------|
| AC3 | `test_system_prompt_emits_module_block_when_path_provided`, `test_system_prompt_module_block_without_name`, `test_system_prompt_no_module_block_when_path_empty_string` | ok |
| AC4 | `test_system_prompt_retrieval_note_only_when_fallback_triggered`, `test_answer_stream_falls_back_when_module_filter_empty` | ok |
| AC5 | `test_system_prompt_no_module_is_byte_identical_to_pre_change_output`, `test_answer_stream_does_not_fall_back_when_module_filter_nonempty` | ok |
| AC7 | `test_post_qa_with_module_name_forwards_to_engine`, `test_post_qa_without_module_name_still_accepted`, `test_post_qa_with_module_name_null_still_accepted` | ok |

Any AC row without a corresponding test is a HIGH finding (missing coverage).

### 2. Test Quality

- Each test asserts *behavior*, not implementation detail. Assertions on substrings in the system prompt are fine; assertions on exact whitespace may be too brittle (flag as MEDIUM if they over-specify).
- The "byte-identical no-module output" test MUST hard-code the expected pre-change string. If it constructs the expected string by calling the same function being tested, it proves nothing — HIGH finding.
- Fallback tests MUST spy on the unfiltered-search path and assert it was/wasn't called. Tests that only check the output text are insufficient — MEDIUM (fixable) finding.

### 3. Isolation & Determinism

- No live DB in unit tests (unit tests must not require the PostgreSQL testcontainer).
- No live Ollama or LanceDB. Both must be mocked or monkeypatched.
- Integration tests may hit the real PostgreSQL testcontainer but must mock Ollama / LanceDB.
- No `time.sleep`, no network calls.

### 4. Conventions

- Read `tests/CLAUDE.md`.
- Test names describe the behavior (`test_<subject>_<verb>_<condition>`).
- Async tests use `pytest.mark.asyncio` (or whatever the project configured).
- No `importlib.reload(orch.config)` — forbidden.

### 5. Coverage of Error Paths

- LanceDB exception path — covered by `test_answer_stream_handles_lancedb_exception_without_claiming_fallback`.
- Empty `module_path` ("" and None) — both covered.
- `module_name=None` while `module_path` set — covered.

### 6. Regression Check

- Run the full unit + integration suite to confirm no existing test broke. Any regression is CRITICAL (pre-existing tests should be green).

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all green.
2. `make test-integration` — all green.
3. `uv run ruff check tests/`

## Severity Levels

- Missing test for an AC: HIGH.
- Test that over-constrains (asserts exact whitespace or stable dict ordering where not required): MEDIUM (fixable).
- Test that asserts nothing load-bearing: HIGH.
- Test that depends on Ollama / LanceDB being up: CRITICAL.

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "CR-00009",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
