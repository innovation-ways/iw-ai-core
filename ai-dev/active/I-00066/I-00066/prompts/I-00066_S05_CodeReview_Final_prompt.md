# I-00066_S05_CodeReview_Final_prompt

**Work Item**: I-00066 -- OSS finding modal too narrow and footer buttons unclear
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident touches no database state — there is no migration step.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00066 --json`.
- `ai-dev/active/I-00066/I-00066_Issue_Design.md`
- `ai-dev/active/I-00066/I-00066_Functional.md`
- All step reports:
  `ai-dev/active/I-00066/reports/I-00066_S01_Frontend_report.md`
  `ai-dev/active/I-00066/reports/I-00066_S02_CodeReview_report.md`
  `ai-dev/active/I-00066/reports/I-00066_S03_Tests_report.md`
  `ai-dev/active/I-00066/reports/I-00066_S04_CodeReview_report.md`
- All files listed in S01 + S03 `files_changed`:
  - `dashboard/static/tailwind.src.css`
  - `dashboard/static/styles.css`
  - `dashboard/templates/fragments/oss_finding_modal.html`
  - `tests/dashboard/test_i00066_oss_modal_styling.py`

## Output Files

- `ai-dev/active/I-00066/reports/I-00066_S05_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of all
implementation work for I-00066. The fix is small and contained but
the holistic view still matters — confirm that the CSS edits, the
template edit, the regenerated compiled CSS, and the new tests all
fit together.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations → CRITICAL findings with `category: "conventions"`.

## Review Checklist

### 1. Completeness vs Design Document

- All three Acceptance Criteria from the design doc are met:
  - **AC1** Modal width ~80vw — `.oss-modal-inner` has
    `max-width: 80vw` in BOTH `tailwind.src.css` and the compiled
    `styles.css`.
  - **AC2** Footer buttons clearly identifiable — the four button
    classes (`.modal-apply`, `.modal-rerun`, `.modal-accept`,
    `.modal-preview`) plus the new `.modal-footer-close` render
    with visible border, consistent padding, hover state, no
    flashy / brand colours. The footer Close button has the new
    class.
  - **AC3** Reproduction + regression test exists at
    `tests/dashboard/test_i00066_oss_modal_styling.py` with the
    four semantic assertions.
- The `36rem` literal is GONE from the `.oss-modal-inner` block in
  both source and compiled CSS.
- The header `×` close button (line 11 of the template) is
  UNCHANGED — `class="modal-close"` only.
- Functional doc (`I-00066_Functional.md`) accurately reflects the
  change in plain language with no file paths or code fences.

### 2. Cross-Agent Consistency

- The class name `modal-footer-close` is identical in
  `tailwind.src.css`, `styles.css`, the template, and the test
  file (no typos like `modal-footer_close` or `modal-close-footer`).
- The semantic value `80vw` is identical everywhere (no `80%`, no
  `80vmin`).

### 3. Integration Points

- The existing JS click handler in `oss_finding_modal.html:335-345`
  matches `ev.target.classList.contains('modal-close')`. The footer
  Close button still has `modal-close` in addition to
  `modal-footer-close`, so the modal still closes when clicked.
- The CSS rules cascade correctly — the new `.modal-footer-close`
  rule does not collide destructively with `.modal-close` styles
  on the same element (the footer Close button has both).
- `make css` was actually run — the compiled `styles.css` reflects
  the source changes. Verify by grep.

### 4. Test Coverage (Holistic)

- The four tests cover the complete fix surface (source CSS,
  compiled CSS, template change, new class definition).
- No false-positive risk: each test would FAIL on `main` (no
  shape-only assertions).
- Run the targeted test:
  `uv run pytest tests/dashboard/test_i00066_oss_modal_styling.py -x`
  — must pass.

### 5. Architecture Compliance

- `dashboard/CLAUDE.md` rules respected: NO docker, NO alembic from
  dashboard code, business logic does not move into routers (no
  routers were touched at all).
- `make css` build step was used (per `dashboard/CLAUDE.md`).

### 6. Security (Cross-Cutting)

- No secrets, credentials, or hardcoded URLs in any changed file.
- No new injection vectors (the change does not touch dynamic
  content).

## Test Verification (NON-NEGOTIABLE)

Run the FULL test suite:

```bash
make test-unit
make test-integration
```

A failing integration test attributable to this change is a
CRITICAL finding (`tests_passed: false`).

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Missing requirement, broken modal/JS handler, integration test fails |
| **HIGH** | Cross-step inconsistency (typo'd class name), missing compiled CSS regeneration, flashy colour added |
| **MEDIUM (fixable)** | Convention violation, formatting drift |
| **MEDIUM (suggestion)** | Improvement |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00066",
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
