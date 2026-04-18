# CR-00009_S06_CodeReview_prompt

**Work Item**: CR-00009 — Chat panel context awareness
**Step Being Reviewed**: S05 (frontend-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/CR-00009/CR-00009_CR_Design.md`
- `ai-dev/active/CR-00009/reports/CR-00009_S05_Frontend_report.md`
- All files listed in the S05 report's `files_changed`

## Output Files

- `ai-dev/active/CR-00009/reports/CR-00009_S06_CodeReview_report.md`

## Context

Review S05 (frontend-impl) changes: chat header label, `data-module-name` propagation, composer payload.

## Review Checklist

### 1. Contract vs AC

- **AC1**: With no module selected (fresh page load on a project), does the header text resolve to exactly `Chat — Architecture`?
- **AC2**: After navigating to a module, does the header text format resolve to exactly `Chat — <path> (<name>)` (with the parens only when `module_name` is present)?
- **AC7**: Is `module_name` included in the POST body when available, and omitted/null when not? Check `composer.js`.

### 2. XSS / Escaping

- `label.textContent = text` (not `innerHTML`) — CRITICAL if this is violated.
- `{{ module.name }}` in Jinja must not use `| safe`. CRITICAL if it does.
- Any reconstruction of HTML strings from `dataset.moduleName` is a HIGH finding — always go through `textContent` or DOM `createElement`.

### 3. Event Wiring

- Does `syncChatHeader` run on both initial load (no `htmx` event yet) AND `htmx:afterSwap` on `#code-content-root`?
- Does the composer's existing `htmx:afterSwap` listener (`composer.js:108-112`) still work? Adding a second listener on the same event is fine, but overwriting the event handler would break the composer chip.

### 4. Module Attribute Propagation (Option A)

- Are BOTH `data-module-path` and `data-module-name` set on `#code-content-root` when a module-detail fragment is swapped in, and cleared when the user navigates back to the architecture view? A stale `data-module-name` (or stale `data-module-path`) on architecture view is HIGH (would make the header and chip lie).
- `code_module_detail.html` must carry `data-module-path="{{ module.path }}"` and `data-module-name="{{ module.name }}"` on `#code-module-detail`, plus a trailing inline `<script>` that mirrors both attrs onto `#code-content-root` and dispatches `iw:code-context-changed`. Verify this exists and runs on every fragment insertion.
- A single `htmx:afterSwap` listener (in `panel.js` or equivalent) resets `#code-content-root`'s data-attrs to `""` on architecture-reset swaps — either `target.id === 'code-components-section'` OR (`target.id === 'code-detail-panel'` AND `!target.querySelector('#code-module-detail')`). Missing this guard or firing it on module-to-module navigation is HIGH.
- Both `syncChatHeader` (panel.js) and `syncContextChip` (composer.js) must listen to `iw:code-context-changed`. If `syncContextChip` is not wired to that event, the composer chip will continue to never appear — CRITICAL (does not deliver the CR's side-effect fix to CR-00008's dead read path, contradicting the design doc's Desired Behavior item 6).
- No new server-side render paths that wrap `#code-content-root` — the mechanism is client-side mirror via inline script, per Option A.

### 5. Conventions

- Read `dashboard/CLAUDE.md`. ES5-compatible vanilla JS, no build step, no dynamic Tailwind classes.
- IIFE style consistent with existing `panel.js` / `composer.js`.
- No new npm dependencies, no import statements in the JS files.

### 6. Tailwind / Layout

- `truncate` class applied to the header label so long paths don't break the flex layout?
- Does the header still render the collapse/close buttons correctly?

### 7. Regression Check

- Chat send flow still works: verify the slash menu, image paste, send button, and streaming wiring are untouched.
- `composer.js::syncContextChip` is unchanged.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `uv run ruff check dashboard/`
3. If practical, open the dashboard and manually confirm header updates (the qv-browser step will verify end-to-end — so manual verification here is best-effort, not blocking).

## Severity Levels

Standard. Use of `innerHTML` or `| safe` for user-controlled strings is CRITICAL. Stale `data-module-name` on architecture view is HIGH. Missing initial-load sync is HIGH (first paint bug).

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00009",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
