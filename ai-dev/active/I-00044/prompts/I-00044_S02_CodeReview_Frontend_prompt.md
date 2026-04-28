# I-00044_S02_CodeReview_Frontend_prompt

**Work Item**: I-00044 — Code View Chat Panel — Ugly Collapse State and Viewport Drift
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00044/I-00044_Issue_Design.md` — design document with root cause and AC
- `ai-dev/active/I-00044/reports/I-00044_S01_Frontend_report.md` — S01 implementation report
- `dashboard/templates/project_code.html` — modified (Bug 2 fix)
- `dashboard/templates/chat/panel.html` — modified (Bug 1 fix)
- `dashboard/static/chat/panel.js` — modified (Bug 1 fix)
- `dashboard/static/chat.css` — modified (Bug 1 fix)
- `dashboard/static/styles.css` — rebuilt by `make css`

## Output Files

- `ai-dev/active/I-00044/reports/I-00044_S02_CodeReview_Frontend_report.md`

## Review Checklist

### Bug 2 — Grid constraint (`project_code.html`)

- [ ] `#page-body` has `lg:grid-rows-[1fr]` in its class list
- [ ] No other layout classes were removed or changed unintentionally
- [ ] `base.html` was NOT modified (the fix must be scoped to `project_code.html`)
- [ ] `code_architecture_view.html` was NOT modified (it already has `h-full overflow-y-auto`)
- [ ] The `scrollIntoView()` calls at lines ~201 and ~206 of `project_code.html` are still present (they now scroll within the left column's overflow container, which is correct)

### Bug 1 — Slide-out toggle tab (`panel.html`, `panel.js`, `chat.css`)

- [ ] The new toggle tab (`#chat-toggle-tab`) is present in `panel.html`
- [ ] The toggle tab contains a chat bubble SVG icon AND a rotated "Chat" text label
- [ ] The toggle tab has an `aria-label` that references "chat panel" and includes the keyboard shortcut `(Cmd+\)`
- [ ] The toggle tab is a `<button>` element (keyboard-accessible, not a `<div>`)
- [ ] Minimum touch target: `min-h-[44px] min-w-[44px]` or equivalent on the toggle
- [ ] The old `#chat-collapse-btn` inside the panel header has been properly removed or repurposed — there must not be TWO collapse toggles
- [ ] The collapsed state (CSS `[data-collapsed="true"]`) shows the expanded tab identity (icon + label)
- [ ] The expanded state shows a minimal collapse indicator
- [ ] Mobile behavior is UNCHANGED: `#chat-close-btn`, `#chat-drawer-open`, `#chat-drawer-backdrop` are all present and unmodified
- [ ] `panel.js:applyCollapsedState()` updates both the toggle tab's aria-label AND the panel's `data-collapsed` attribute
- [ ] The keyboard shortcut `Cmd+\` / `Ctrl+\` still works (the keydown listener in `panel.js` calls `togglePanel()`)
- [ ] Resize handle (`#chat-resize-handle`) is still present and unmodified

### CSS / Tailwind

- [ ] New CSS rules in `chat.css` do not conflict with existing rules
- [ ] `dashboard/static/styles.css` was rebuilt (`make css` was run) — check for `lg:grid-rows-[1fr]` in the generated output if it's a new class
- [ ] No dynamic class construction that would break Tailwind JIT purging

### Semantic Correctness vs Shape

- [ ] The toggle tab shows a literal "Chat" string (not just an SVG with no text label)
- [ ] The `aria-label` is not empty and is not just the default "button" label

### Security & Accessibility

- [ ] No `innerHTML` with unsanitised user content added
- [ ] All interactive elements are keyboard-focusable
- [ ] ARIA labels are present and correct on the new toggle tab

## Severity Guide

| Severity | Examples |
|----------|---------|
| CRITICAL | Mobile drawer broken; keyboard shortcut lost; XSS vector introduced |
| HIGH | Two collapse buttons present (duplicate); collapsed state still shows bare chevron; `lg:grid-rows-[1fr]` missing |
| MEDIUM | Touch target below 44 px; aria-label missing the shortcut hint; `make css` not run |
| LOW | Minor CSS nit; log statement left in JS |

## Output

Write the report to `ai-dev/active/I-00044/reports/I-00044_S02_CodeReview_Frontend_report.md`.

List all findings with: **Severity** | **File:line** | **Description** | **Recommendation**.

End the report with one of:
- `APPROVED` — no CRITICAL or HIGH findings
- `APPROVED WITH NOTES` — only LOW/MEDIUM findings
- `NEEDS REWORK` — one or more CRITICAL or HIGH findings (list them explicitly)

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00044",
  "completion_status": "complete",
  "review_outcome": "APPROVED|APPROVED WITH NOTES|NEEDS REWORK",
  "critical_findings": 0,
  "high_findings": 0,
  "medium_findings": 0,
  "low_findings": 0,
  "blockers": [],
  "notes": ""
}
```
