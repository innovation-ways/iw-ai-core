# I-00089 S02 CodeReview Frontend — Report

## Summary

**pass** — S01 correctly fixes both Bug A and Bug B using template + CSS only. All acceptance criteria are met; no regressions. One LOW observation about Tailwind utility classes not in the prebuilt stylesheet, but the distinguishing visual treatment is correctly delivered via plain CSS in `chat.css` so it functions correctly regardless.

## Findings

| Severity | Area | Finding | File:line | Required Fix |
|----------|------|---------|-----------|--------------|
| LOW | Tailwind classes | The button now uses `ml-1` and `w-4 h-4` (Tailwind margin-left-1 and 16px icon sizing). Neither appears in the prebuilt `dashboard/static/styles.css`. The distinguishing visual treatment (border, background, hover) is correctly delivered via the plain-CSS rule in `chat.css` using the custom `chat-assistant-collapse-btn-distinct` class, so the button is still visually distinguished. However `ml-1` and `w-4 h-4` will have no effect until `make css` is run or the worktree's Tailwind is synced. | `panel.html:67` | None — the functional fix (distinguishable button) is delivered via plain CSS in `chat.css` (lines 254-262). `ml-1` and `w-4 h-4` are cosmetic augmentations that degrade gracefully. |

(Empty table above the separator is acceptable if review is clean.)

## Acceptance Criteria Traceability

| AC | Covered by | Status |
|----|------------|--------|
| AC1 | Bug A hide-rule extension in `panel.html` `<style>` block (line 12: `#chat-assistant-panel[data-collapsed="true"] #chat-assistant-collapse-btn { display: none; }`) | **pass** |
| AC2 | Bug B `title` attribute (`title="Collapse panel"`) + distinguishing class marker (`chat-assistant-collapse-btn-distinct`) + supporting CSS in `chat.css` (lines 254-262) | **pass** |

## Detailed Checklist

### Correctness

| Item | Status | Evidence |
|------|--------|----------|
| Bug A — inline `<style>` block extends `display:none` selector to include `#chat-assistant-collapse-btn` | ✅ pass | `panel.html:12`: `#chat-assistant-panel[data-collapsed="true"] #chat-assistant-collapse-btn { display: none; }` — correctly comma-separated from the other selectors, no stray semicolons |
| Bug B — collapse button has `title` attribute | ✅ pass | `panel.html:69`: `title="Collapse panel"` |
| Bug B — collapse button has distinguishing class marker | ✅ pass | `panel.html:67`: `class="… chat-assistant-collapse-btn-distinct …"` |
| `aria-label` preserved | ✅ pass | `panel.html:68`: `aria-label="Collapse AI Assistant panel (Ctrl+/)"` — unchanged from pre-fix |
| SVG path preserved | ✅ pass | `panel.html:71`: `d="M15 19l-7-7 7-7"` — unchanged |
| JS unchanged | ✅ pass | `git diff main -- dashboard/static/chat_assistant/chat.js` — zero output |
| Expand rail unchanged | ✅ pass | `panel.html:76-88` — `#chat-assistant-expand-rail` block untouched |

### Scope adherence

| Item | Status | Evidence |
|------|--------|----------|
| `git diff main --name-only` contains only allowed paths | ✅ pass | Only `dashboard/static/chat_assistant/chat.css` and `dashboard/templates/chat_assistant/panel.html` |
| No new Tailwind classes require `make css` | ⚠️ LOW | `ml-1` and `w-4 h-4` are not in prebuilt `styles.css`; distinguishing treatment works via plain CSS in `chat.css` |

### Accessibility

| Item | Status | Evidence |
|------|--------|----------|
| Tab order through header unchanged (tray-toggle → history-toggle → new-btn → collapse-btn) | ✅ pass | DOM order at `panel.html:39-73` is unchanged |
| `title` is in addition to, not replacement for, `aria-label` | ✅ pass | Both present: `aria-label="Collapse AI Assistant panel (Ctrl+/)"` + `title="Collapse panel"` |
| Collapse button remains keyboard-focusable | ✅ pass | No `tabindex="-1"` added; standard `<button>` element |

### Behaviour preservation

| Item | Status | Evidence |
|------|--------|----------|
| Ctrl+/ keybinding unchanged | ✅ pass | No changes to `chat.js`; handler at `chat.js:937-942` is intact |
| Nav-bar toggle button unchanged | ✅ pass | No changes to `chat.js`; handler at `chat.js:965-968` is intact |
| Expand rail opens the panel | ✅ pass | No changes to expand rail block or its JS wiring |

### Cross-page check

The panel template is included via `{% include "chat_assistant/panel.html" %}` from `dashboard/templates/base.html:78`, which is inherited by all dashboard pages. All CSS rules added by the fix are scoped to `#chat-assistant-panel` (the `[data-collapsed]` attribute selector) or to the `#chat-assistant-panel:not([data-collapsed="true"])` context — they cannot leak to unrelated buttons elsewhere on the dashboard. ✅ pass

### Preflight gate sanity

S01's report shows `preflight.format: ok`, `preflight.typecheck: ok`, `preflight.lint: ok`. ✅ all green.

## Decision

- **`complete`** — no CRITICAL or HIGH findings.