# I-00067_S01_Frontend_prompt

**Work Item**: I-00067 -- Recent Activity messages need truncation + click-to-expand popup
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy. No container operations are required for this step. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch Alembic migrations.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00067 --json` for the current step list.
- `ai-dev/active/I-00067/I-00067_Issue_Design.md` — Design document (READ FIRST)
- `ai-dev/active/I-00067/I-00067_Functional.md` — Functional design (read for user-facing intent)
- `ai-dev/active/I-00067/evidences/pre/I-00067-recent-activity.png` — Pre-fix screenshot
- `ai-dev/active/I-00067/evidences/pre/I-00067-snapshot.yml` — Pre-fix accessibility snapshot
- `dashboard/templates/pages/project/dashboard.html` — Template containing the buggy Recent Activity card (line 121 is the problem render site)
- `dashboard/templates/fragments/oss_finding_modal.html` — Reference modal pattern (overlay + inner card + close + ESC + click-outside + focus trap)
- `dashboard/CLAUDE.md` — Dashboard conventions (Jinja2 + htmx + prebuilt Tailwind)
- `CLAUDE.md` — Project conventions (especially the `make css` requirement)

## Output Files

- `ai-dev/active/I-00067/reports/I-00067_S01_Frontend_report.md` — Step report

## Context

You are implementing the only fix step for **I-00067 — Recent Activity messages need truncation + click-to-expand popup**.

The Recent Activity card on the per-project dashboard renders each event's `message` field as a single inline `<span>` with no length cap. Long failure messages and tracebacks dominate the card. There is no popup affordance for viewing the full message.

Read the design document end-to-end before writing any code, especially the Acceptance Criteria, Steps to Reproduce, and Affected Components sections.

## Requirements

### 1. Truncate long messages on the project dashboard

In `dashboard/templates/pages/project/dashboard.html`, change the rendering of `event.message` in the Recent Activity loop (currently around line 121).

- Determine the displayed text and whether to render an expand affordance based on the **codepoint length** of the original message (Python `len()` semantics — Jinja2's `length` filter is fine):
  - If `event.message` is `None` or empty, render `event.event_type` exactly as today, with NO truncation logic.
  - If `len(event.message) <= 100`, render `event.message` verbatim. Do NOT append `...`. Do NOT add an expand affordance. Do NOT emit any modal payload for this row.
  - If `len(event.message) > 100`, render the first 100 codepoints of `event.message` followed by the literal three ASCII dots `...` (NOT the `…` Unicode ellipsis). Make this row clickable to open the popup. Embed the full untruncated message in the DOM so JavaScript can read it on click — choose ONE of:
    - a `data-full-text` attribute on the trigger element (HTML-escaped; use Jinja2's default autoescape — do NOT mark safe), OR
    - a sibling hidden `<template>` element keyed by a stable identifier per row.
  - Preferred approach: `data-full-text` attribute on the trigger element. Use the existing autoescape — do NOT manually escape and do NOT use `|safe`.
- Add a CSS class on the trigger element so tests can target it deterministically (e.g., `activity-message-truncated`). The same class hosts cursor/hover styling. Do NOT add hover/cursor styling to non-truncated rows.
- Preserve all existing behaviour for the entity-link badge (the `<a>` tag for batch / doc_job / work_item rows in lines 100-119). Do NOT change link routing in this step.

### 2. Add a generic activity-text modal partial

Create `dashboard/templates/fragments/activity_text_modal.html`. Structurally model it on `dashboard/templates/fragments/oss_finding_modal.html` (overlay + inner card + close button + ESC + click-outside + focus trap), but:

- Use UNIQUE element IDs (e.g., `activity-text-modal-overlay`, `activity-text-modal`, `activity-text-modal-body`). Do NOT reuse `oss-modal-*` IDs/classes — both modals must be able to coexist on a future shared page.
- The body shows ONE block: a `<pre>` (or `<div>` with `white-space: pre-wrap`) containing the full untruncated text, populated by JavaScript on open.
- Include a close button labelled `×` and the dismissal behaviours: ESC, click on overlay/backdrop, click on close button, click outside the inner card.
- Implement a focus trap matching the OSS pattern. On close, restore focus to the element that opened the modal (`lastFocusedElement` pattern — see `oss_finding_modal.html:107-126`).
- Include the partial from the project dashboard template (e.g., `{% include "fragments/activity_text_modal.html" %}`) so it lives on the page and is ready when the user clicks a truncated row.

### 3. Wire the click handler

Inside the modal partial's `<script>` block (or a tiny inline script in the dashboard template), attach a single delegated `click` listener (e.g., on `document` filtered by `.activity-message-truncated`) that:

1. Reads `data-full-text` from the trigger element.
2. Populates the modal body with that text using `textContent` (NOT `innerHTML`) — never inject as HTML.
3. Opens the modal (mirror the `aria-hidden` toggling and `body.style.overflow = 'hidden'` from the OSS pattern).

Do NOT introduce a JS module or build step. Vanilla JS only, in a single `<script>` block, matching the style of the existing OSS modal scripts.

### 4. Rebuild Tailwind CSS

If you add any new Tailwind utility classes, run `make css` to regenerate `dashboard/static/styles.css`. The generated file is committed to the repo.

### 5. Behaviour-preserving for short messages

Manually verify (read your diff and re-read the template) that:
- A row with a 100-character message renders exactly as today: no `...`, no `data-full-text`, no `activity-message-truncated` class, no cursor change.
- A row with a 101-character message renders 100 chars + `...` and IS clickable.
- The `if event.entity_id and event.entity_type == 'batch'` chain in lines 100-119 is untouched.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md` for:

- Jinja2 + htmx + prebuilt Tailwind CSS conventions
- Where fragments live (`dashboard/templates/fragments/`) and that they MUST NOT extend `base.html`
- Tailwind JIT purging rules — avoid dynamic class construction
- The `make css` build step

Match the visual style of the existing OSS modal (border, rounded corners, padding, dark/light themes via Tailwind tokens like `bg-card`, `border-border`, `text-foreground`).

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write the failing integration test FIRST in `tests/integration/test_i00067_recent_activity_truncation.py` (or extend it if S03 will write a more comprehensive suite — but you MUST have at least one failing test that proves the bug exists before changing the template).
2. **GREEN**: Make the template change to pass it.
3. **REFACTOR**: Clean up.

Do not skip the RED phase. The reproduction test must exist and fail before the template edit.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run these in order and fix any issues they report:

1. `make format` — auto-fixes formatting drift.
2. `make typecheck` — must report zero errors involving the files you touched.
3. `make lint` — must report zero errors. Note: `make lint` also runs `node --check` on dashboard JS — your inline modal script must pass.

If you regenerate `styles.css` via `make css`, also run `make lint` again afterwards.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-integration` to verify your reproduction test passes and no dashboard tests regress.
2. Run `make test-unit` to verify no unit-level regressions.
3. Do NOT report `tests_passed: true` unless ALL tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00067",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/pages/project/dashboard.html",
    "dashboard/templates/fragments/activity_text_modal.html",
    "dashboard/static/styles.css",
    "tests/integration/test_i00067_recent_activity_truncation.py"
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
