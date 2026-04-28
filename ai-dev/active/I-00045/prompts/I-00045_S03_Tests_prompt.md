# I-00045_S03_Tests_prompt

**Work Item**: I-00045 — OSS Status Widget and Page: Ugly Layout and Raw JSON Rendering
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations policy

Full policy: docs/IW_AI_Core_Agent_Constraints.md. Tests use testcontainers only — NEVER connect to port 5433.

---

## Input Files

- Design document: `ai-dev/active/I-00045/I-00045_Issue_Design.md`
- S01 report: `ai-dev/active/I-00045/reports/I-00045_S01_Frontend_report.md`
- Fixed template: `dashboard/templates/fragments/oss_status_frame.html`
- Fixed template: `dashboard/templates/pages/project/oss.html`
- Test conventions: `tests/CLAUDE.md`, `tests/conftest.py`
- Existing dashboard tests for reference: `tests/dashboard/`

## Output Files

- New test file (location per `tests/CLAUDE.md` — likely `tests/dashboard/test_oss_status_rendering.py`)
- `ai-dev/active/I-00045/reports/I-00045_S03_Tests_report.md`

---

## Context

Write a reproduction test and regression tests for I-00045. These tests verify that the OSS status dashboard widget and OSS compliance page render correctly — specifically that:
- The raw `summary_json` dict is **never** exposed as text in the HTML output
- The "OSS STATUS" heading is a link to the OSS page
- The OSS page uses CSS-styled status dots, not emoji characters

Read `tests/CLAUDE.md` and `tests/conftest.py` before writing any tests to understand:
- Which conftest fixtures are available
- How dashboard tests use `TestClient`
- How to create ORM objects for `Project` and `OssScan` in tests

---

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "summary" in response.text` (shape only)
- GOOD: `assert "{'skip'" not in response.text` (semantic — verifies raw dict is absent)
- GOOD: `assert "50 passed" in response.text` (semantic — verifies specific expected label)
- GOOD: `assert "🔴" not in response.text` (semantic — verifies emoji is absent)

---

## Requirements

### 1. Reproduction Test — Dashboard widget raw JSON

Write a test that would have FAILED against the pre-fix code and PASSES against the fixed code.

The test must:
1. Create a `Project` and `OssScan` with a known `summary_json` dict (e.g., `must_fail=4`, `must_pass=15`, `should_fail=9`, `should_pass=31`, `may_pass=4`)
2. Call `GET /project/{id}/` via TestClient
3. Assert that the raw JSON markers do NOT appear in the response HTML:
   - `"{'skip'"` must NOT be in `response.text`
   - `"must_fail"` must NOT be in `response.text`
   - `"'total'"` must NOT be in `response.text`
4. Assert that the formatted label DOES appear:
   - `"passed"` must be in `response.text`

Name the test `test_i00045_oss_widget_no_raw_json`.

### 2. Regression Test — Formatted counts are correct

Write a test that verifies the specific computed values:
1. Create an `OssScan` with `must_pass=15`, `should_pass=31`, `may_pass=4`, `must_fail=4`, `should_fail=9`
2. Call `GET /project/{id}/`
3. Assert `"50 passed"` is in `response.text` (15 + 31 + 4 = 50)
4. Assert `"4 critical"` is in `response.text`
5. Assert `"9 warnings"` is in `response.text`

Name the test `test_i00045_oss_widget_formatted_counts`.

### 3. Regression Test — Zero counts are omitted

Write a test for the zero-count edge case:
1. Create an `OssScan` with `must_pass=50`, `should_pass=0`, `may_pass=0`, `must_fail=0`, `should_fail=0`
2. Call `GET /project/{id}/`
3. Assert `"50 passed"` is in `response.text`
4. Assert `"critical"` is NOT in `response.text` (must_fail == 0, segment omitted)
5. Assert `"warnings"` is NOT in `response.text` (should_fail == 0, segment omitted)

Name the test `test_i00045_oss_widget_zero_counts_omitted`.

### 4. Regression Test — OSS STATUS heading links to OSS page

Write a test that verifies the heading is a link:
1. Create a `Project` with OSS enabled (and an `OssScan` or just the project row)
2. Call `GET /project/{id}/`
3. Parse the response HTML and assert that an `<a>` element with `href="/project/{id}/oss"` exists
4. Assert that the link text contains "OSS" (case-insensitive)

Name the test `test_i00045_oss_heading_is_link`.

### 5. Regression Test — OSS page has no emoji status circles

Write a test for the OSS page:
1. Create a `Project` and a completed `OssScan` with `pill_color=OssPillColor.red`
2. Call `GET /project/{id}/oss`
3. Assert `"🔴"` is NOT in `response.text`
4. Assert `"🟡"` is NOT in `response.text`
5. Assert `"🟢"` is NOT in `response.text`

Name the test `test_i00045_oss_page_no_emoji_status`.

---

## Test Conventions

- Follow the patterns in `tests/CLAUDE.md` exactly
- Use the fixture helpers from `tests/conftest.py` (check what `make_project`, `make_oss_scan`, or equivalent helpers exist; if they don't, create minimal inline setup)
- Use `TestClient` (sync) — do NOT use `httpx.AsyncClient` unless the existing tests do
- Do NOT mock the database in integration tests — use testcontainers per `CLAUDE.md` rules
- All tests in this file should be independent (no shared state between tests)

---

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fix formatting
2. `make typecheck` — zero errors on files you touched
3. `make lint` — zero errors
4. `make test-unit` — all tests pass (including your new ones)

---

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00045",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_oss_status_rendering.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
