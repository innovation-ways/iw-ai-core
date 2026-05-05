# I-00067_S02_CodeReview_Frontend_prompt

**Work Item**: I-00067 -- Recent Activity messages need truncation + click-to-expand popup
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Input Files

- `uv run iw item-status I-00067 --json` — current step state
- `ai-dev/active/I-00067/I-00067_Issue_Design.md` — Design document
- `ai-dev/active/I-00067/reports/I-00067_S01_Frontend_report.md` — S01 implementation report
- All files listed in S01's `files_changed`
- `dashboard/templates/fragments/oss_finding_modal.html` — Reference modal pattern for comparison

## Output Files

- `ai-dev/active/I-00067/reports/I-00067_S02_CodeReview_report.md` — Review report

## Context

Review the frontend fix for I-00067. The intended behaviour is:

- Messages with `len > 100` codepoints render as `<first 100 chars>...` with a click-to-expand affordance and a hidden full-text payload.
- Messages with `len <= 100` codepoints render verbatim, with NO `...`, NO trigger affordance, and NO modal payload.
- Empty messages fall back to `event.event_type`.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files in S01's `files_changed`:

```bash
make lint
make format
```

Report any new violations as CRITICAL findings with `category: conventions`.

## Review Checklist

### 1. Architecture Compliance

- Is the new modal partial in `dashboard/templates/fragments/`?
- Does the fragment NOT extend `base.html`?
- Is the new partial included from the project dashboard template?
- Are unique IDs used (no collision with `oss-modal-*` / `oss-finding-modal*`)?
- Is the rendering logic in the template (not JS-rendered)?

### 2. Correctness of the truncation rule

- Cutoff is exactly 100 codepoints (not bytes, not 99, not 101).
- Suffix is the literal three ASCII dots `...`, NOT the `…` Unicode ellipsis character.
- Boundary behaviour: `len == 100` → no truncation, no `...`. `len == 101` → truncate to 100 + `...`.
- Empty / `None` message → fall back to `event.event_type` (no truncation logic applied).
- For short messages, the trigger class (e.g., `activity-message-truncated`), `data-full-text` attribute, cursor styling, and click handler binding are all absent.

### 3. Escape safety

- The `data-full-text` attribute (or `<template>` payload) uses Jinja2's default autoescape — no `|safe`, no manual escape that could double-encode.
- The modal body is populated via `element.textContent = ...`, NOT `innerHTML`. Confirm by reading the JS.
- A message containing HTML characters (e.g., `<script>alert(1)</script>`) is escaped both in the inline 100-char preview and inside `data-full-text`.

### 4. Accessibility

- Modal has `role="dialog"`, `aria-modal="true"`, `aria-hidden` toggled correctly.
- ESC key closes the modal.
- Click outside the inner card closes the modal.
- Focus moves into the modal on open.
- Focus returns to the trigger element on close (`lastFocusedElement` pattern).
- Tab key cycles within the modal (focus trap).

### 5. No regressions

- The entity-link `<a>` tag for `batch` / `doc_job` / `work_item` rows is unchanged in lines 100-119.
- The empty-state branch (`No recent activity.`) is unchanged.
- Tailwind CSS is rebuilt if new utility classes were introduced. Confirm `dashboard/static/styles.css` is regenerated and committed.

### 6. Project Conventions

- Vanilla JS, no module bundler, single `<script>` block (matching the OSS modal style).
- No new dependencies in `pyproject.toml` or `package.json`.
- `make css` re-run if Tailwind classes changed.
- Read `dashboard/CLAUDE.md` for any other rules.

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration` to verify dashboard tests pass.

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00067",
  "step_reviewed": "S01",
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
