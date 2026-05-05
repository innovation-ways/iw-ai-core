# I-00065_S05_CodeReview_Final_prompt

**Work Item**: I-00065 -- Code-view chat panel — "+ New" visible when collapsed and duplicates greeting
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03 (frontend fix + tests)

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
- `ai-dev/active/I-00065/I-00065_Functional.md`
- All implementation reports under `ai-dev/active/I-00065/reports/I-00065_S0[1-3]_*_report.md`
- All per-agent code review reports under `ai-dev/active/I-00065/reports/I-00065_S0[2,4]_CodeReview_report.md`
- All files listed in implementation reports' `files_changed`:
  - `dashboard/templates/chat/panel.html`
  - `dashboard/static/chat/panel.js`
  - `tests/dashboard/test_chat_panel_template.py`
  - `tests/dashboard/test_chat_panel_empty_state.py`

## Output Files

- `ai-dev/active/I-00065/reports/I-00065_S05_CodeReview_Final_report.md`

## Context

You are performing the final cross-agent review of all implementation work for **I-00065**. Per-agent reviews (S02, S04) have already covered each step in isolation; your job is to look at the picture as a whole and catch issues that cross step boundaries.

Read the design doc, functional doc, all implementation and review reports, and all changed files.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in the changed files → CRITICAL findings with `category: "conventions"`.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs Design Document

- AC1 (Bug 1: "+ New" hidden when collapsed) — is the CSS selector clause actually present in `panel.html`?
- AC2 (Bug 2: exactly one greeting after any number of clicks) — does `showEmptyState` actually remove pre-existing `#chat-empty-state` before insertion?
- AC3 (Regression tests exist) — are both named tests present and passing?
- File Manifest table in the design doc — are all listed paths present?

### 2. Cross-Step Consistency

- The `showEmptyState` JS guard wording (e.g. `if (existingEmpty) existingEmpty.remove();`) and the test's `assert` pattern (e.g. checking for that exact idiom) — do they agree? If S03 asserts a more permissive pattern than what S01 actually wrote, the test would still pass but would not protect against a partial-fix regression. Flag any mismatch.

### 3. Integration Points

- Confirm `dashboard/static/chat/panel.js` is still referenced by the page (search the dashboard templates) — the fix is moot if the script is no longer loaded.
- Confirm the `#chat-empty-state` ID is still unique in the static markup of `panel.html` (one `<div id="chat-empty-state">` only).
- Confirm the CSS selector list in `panel.html` is syntactically valid (commas, single trailing `{ display: none; }`, no orphan selector).

### 4. Test Coverage (Holistic)

- Both new tests have correct names matching AC3.
- Tests do not import or instantiate live DB sessions.
- The qv-browser step (S15) covers the end-to-end browser path; per-CR-00023 the QV gates plus qv-browser are sufficient — do NOT require additional Selenium tests.

### 5. Architecture Compliance

- Read `CLAUDE.md` and `dashboard/CLAUDE.md`. The fix respects the dashboard layer's "no docker, no migrations from dashboard" rules trivially (none invoked).
- No file outside the manifest's `scope.allowed_paths` should have been touched.

### 6. Security (Cross-Cutting)

- No new innerHTML construction from untrusted input. (The greeting `innerHTML` uses only string literals — same as the pre-fix code.)

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make test-unit`.
2. Run `make test-frontend`.
3. Run `make test-integration` (the full integration suite — incidents merge through every gate).
4. Report all three results in the contract.

## Severity Levels

Same five-tier scale as S02.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00065",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
