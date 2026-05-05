# I-00065_S04_CodeReview_prompt

**Work Item**: I-00065 -- Code-view chat panel — "+ New" visible when collapsed and duplicates greeting
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Same policy as the rest of this work item.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident does not involve migrations.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00065 --json`.
- `ai-dev/active/I-00065/I-00065_Issue_Design.md`
- `ai-dev/active/I-00065/reports/I-00065_S03_Tests_report.md`
- `tests/dashboard/test_chat_panel_template.py`
- `tests/dashboard/test_chat_panel_empty_state.py`

## Output Files

- `ai-dev/active/I-00065/reports/I-00065_S04_CodeReview_report.md`

## Context

You are reviewing the test coverage produced in S03. Both bugs in I-00065 are tiny and frontend-only; the regression tests must (a) fail against the pre-fix code, (b) pass against the fixed code, and (c) verify SEMANTIC correctness, not just file-content shape.

Read the design's "Test to Reproduce" and "Acceptance Criteria" sections, then the S03 report, then the two new test files.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in the changed files → CRITICAL findings with `category: "conventions"`.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Semantic correctness (CRITICAL — I003 lesson)

For each test, confirm the assertion would FAIL if the bug were re-introduced. Mental sanity check:

**Bug 1 test** — Would it fail if someone removed `#chat-new-btn` from the `[data-collapsed="true"]` selector list?

- BAD assertion (would falsely pass): `assert "chat-new-btn" in PANEL_HTML` — passes whether or not the button is hidden.
- GOOD assertion (correctly fails): asserts the literal selector clause `#chat-panel[data-collapsed="true"] #chat-new-btn` is present in the `<style>` block.

**Bug 2 test** — Would it fail if someone removed the pre-existing-element-removal call from `showEmptyState`?

- BAD (false-pass): `assert ".remove()" in PANEL_JS` — matches the pre-existing `articles.forEach(... a.remove() ...)` call regardless of the fix.
- GOOD: slices `showEmptyState`'s function body and asserts BOTH a `#chat-empty-state` lookup AND a `.remove()` call AND that the lookup precedes the insertion.

If either test is shape-only, raise a CRITICAL `category: "testing"` finding.

### 2. Test Hygiene

- File names match `tests/CLAUDE.md` conventions (`test_*.py` under `tests/dashboard/`).
- Tests are deterministic (no time/random/CWD dependence — paths are derived from `__file__`).
- No live DB connection (`tests/CLAUDE.md`'s "NEVER connect to live DB" rule).
- No new fixtures added outside this incident's scope.

### 3. Test Names

- `test_i00065_new_button_hidden_when_collapsed` exists.
- `test_i00065_show_empty_state_removes_existing_before_insert` exists.

If either is missing or renamed, that's a HIGH finding (acceptance-criterion AC3 names them explicitly).

### 4. Scope

Only the four files in `scope.allowed_paths` should have been touched. Anything else → CRITICAL.

### 5. Lint / Type / Format

The new test files must pass `make lint`, `make typecheck`, and `make format-check` cleanly.

## Test Verification (NON-NEGOTIABLE)

1. Run the two new tests directly:

   ```bash
   uv run pytest tests/dashboard/test_chat_panel_template.py tests/dashboard/test_chat_panel_empty_state.py -v
   ```

2. Run `make test-frontend` to ensure no regression in the dashboard suite.
3. Run `make test-unit`.
4. Report results.

## Severity Levels

Same five-tier scale as S02.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00065",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
