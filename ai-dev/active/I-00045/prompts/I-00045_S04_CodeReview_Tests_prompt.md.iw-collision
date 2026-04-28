# I-00045_S04_CodeReview_Tests_prompt

**Work Item**: I-00045 — OSS Status Widget and Page: Ugly Layout and Raw JSON Rendering
**Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits / Migrations policy

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Input Files

- Design document: `ai-dev/active/I-00045/I-00045_Issue_Design.md`
- S03 report: `ai-dev/active/I-00045/reports/I-00045_S03_Tests_report.md`
- New test file: `tests/dashboard/test_oss_status_rendering.py`
- Test conventions: `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00045/reports/I-00045_S04_CodeReview_Tests_report.md`

---

## Context

Review the S03 test implementation for I-00045. Focus on semantic correctness (the lesson from I003) and test isolation.

---

## Review Checklist

### Semantic Correctness (I003 Lesson — MOST IMPORTANT)

- [ ] Tests do NOT only check that a key or element exists (shape checking)
- [ ] `test_i00045_oss_widget_no_raw_json` explicitly asserts raw dict markers are absent: `"{'skip'"`, `"must_fail"`, `"'total'"` are NOT in `response.text`
- [ ] `test_i00045_oss_widget_formatted_counts` asserts specific count strings: `"50 passed"`, `"4 critical"`, `"9 warnings"` ARE in `response.text` (not just that "passed" exists)
- [ ] `test_i00045_oss_widget_zero_counts_omitted` asserts that `"critical"` and `"warnings"` are NOT in the response when counts are zero
- [ ] `test_i00045_oss_heading_is_link` asserts the href value is `/project/{id}/oss` — not just that an `<a>` tag exists
- [ ] `test_i00045_oss_page_no_emoji_status` asserts the specific emoji characters `🔴`, `🟡`, `🟢` are absent

### Reproduction Test Quality

- [ ] `test_i00045_oss_widget_no_raw_json` is a genuine reproduction test — it would have failed against pre-fix code
- [ ] The test comment or docstring states "FAIL before fix, PASS after fix"

### Test Isolation

- [ ] Each test creates its own project/scan data — no shared state between tests
- [ ] No live DB (port 5433) connections — only testcontainer or TestClient with in-memory/test DB

### Coverage

- [ ] All five acceptance criteria from the design doc have at least one corresponding test
- [ ] Edge case for zero counts (AC1 edge case) is tested

### Convention Compliance

- [ ] Test file is in the correct location per `tests/CLAUDE.md`
- [ ] Tests use the same fixture helpers and `TestClient` pattern as existing dashboard tests

---

## Severity Scale

- **CRITICAL**: Tests check only shape (e.g., `"passed" in response.text` without checking the count); `test_i00045_oss_widget_no_raw_json` would also pass against pre-fix code
- **HIGH**: A dict key access pattern in the test setup would silently suppress a bug (e.g., wrong summary_json values used)
- **MEDIUM**: Missing coverage for zero-counts edge case or emoji check
- **LOW**: Docstring missing; test name doesn't follow naming convention

---

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00045",
  "completion_status": "complete|partial|blocked",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "location": "file:line",
      "description": "What is wrong",
      "suggestion": "How to fix"
    }
  ],
  "approved": true,
  "notes": ""
}
```

Set `approved: true` if there are no CRITICAL or HIGH findings.
