# CR-00010_S06_CodeReview_prompt

**Work Item**: CR-00010 — Research items auto-complete without manual approval
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/CR-00010/CR-00010_CR_Design.md`
- `ai-dev/active/CR-00010/reports/CR-00010_S05_Tests_report.md`
- All files listed in the S05 `files_changed`
- `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00010/reports/CR-00010_S06_CodeReview_report.md`

## Context

Review the test coverage added / updated by S05. The job is to confirm every AC is tested and every test is well-written.

## Review Checklist

### 1. AC Coverage Map

- Read the S05 report's `ac_coverage` map.
- For each AC (AC1..AC10), open the referenced test and confirm it actually exercises the claimed behavior. A test that claims to cover AC3 but never calls `iw doc-update` is a CRITICAL finding.
- Missing AC: CRITICAL finding + `missing_requirements` entry.
- AC8 (dashboard hides approve/unapprove) and AC10 (skill doc) are allowed to be covered by S14 (browser) / manual review respectively — confirm this is noted in the S05 report and is not silently ignored.

### 2. Test Quality

- **Isolation**: integration tests use the testcontainer fixture, not the live DB (port 5433). Any `localhost:5433` string in a test is CRITICAL per `CLAUDE.md`.
- **No mocking the DB in integration tests**: CRITICAL per `CLAUDE.md`.
- **No `importlib.reload(orch.config)`**: CRITICAL per `CLAUDE.md`.
- **psycopg driver**: testcontainer URLs use `postgresql+psycopg://` (v3), not `psycopg2`. HIGH if wrong.
- **Test names** follow the `test_<behavior>_<condition>` pattern.
- **Assertions**: exact substrings from the AC (e.g., `"Cannot approve research items"`) are used literally, not paraphrased. A paraphrase is MEDIUM — the AC specifies the substring.

### 3. Pre-Existing Test Updates

- The S01 report listed the pre-existing tests that fail under the new behavior. Every one of them must be either (a) updated to match the new contract, or (b) removed with a justification in the S05 report.
- `grep -rn "WorkItemType.Research" tests/` AND `grep -rn "R-0000" tests/` AND `grep -rn "'research'" tests/` — cross-check against what S05 actually touched. Missed files are HIGH.

### 4. No Skipped / xfail Tests

- `grep -rn "pytest.mark.skip\|pytest.mark.xfail" tests/` on the new / updated tests. Any `skip` or `xfail` marker added in this CR is CRITICAL (it hides a real failure).

### 5. Regression Surface

- Existing non-research tests still pass unchanged. If S05 modified any non-research test to fit new fixtures, inspect the diff — a non-research test that started relying on a research-specific helper is LOW churn; breaking a non-research assertion is HIGH.

### 6. Idempotency & Edge Cases

- AC4 (`doc-update` idempotent on completed research) has a test. Missing is HIGH.
- AC5 (`doc-update` on non-research does not auto-complete) has a test. Missing is HIGH.
- Edge case: `iw doc-update` on a research `doc_id` that has NO matching work item — test exists and asserts the command still exits 0 with `work_item_auto_completed: false`. Missing is MEDIUM (not an AC but it's the "ad-hoc research doc" path called out in the design notes).

### 7. Test Code Quality

- Helpers are reused from `tests/conftest.py` where possible.
- No hardcoded project IDs — use the fixture-provided project.
- No time-based `sleep()` calls.
- No unused imports.

### 8. Conventions (`tests/CLAUDE.md`)

- Unit tests under `tests/unit/` have no DB session. Integration tests under `tests/integration/` get their session from the fixture.
- FTS trigger: if a new integration test creates the schema fresh (unusual), it must apply `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `create_all`. Most tests reuse the shared fixture; flag HIGH if a test creates its own schema without the trigger.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all green.
2. `make test-integration` — all green.
3. `uv run ruff check tests/`
4. `uv run ruff format --check tests/`

Any failure is CRITICAL.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00010",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
