# CR-00008 S04 — Code Review of S03 (Layout / Scroll / Composer / Keyboard / Image paste)

## What Was Done

Reviewed S03 frontend implementation against the CR-00008 design spec and checklist. Read all S03 output files, templates, JS/CSS assets, and test suite. Ran `ruff check dashboard/` and `uv run pytest tests/dashboard/test_chat_templates.py -v`.

## Files Reviewed

- `dashboard/templates/project_code.html`
- `dashboard/templates/chat/panel.html`
- `dashboard/templates/chat/composer.html`
- `dashboard/static/chat.css`
- `dashboard/static/chat/panel.js`
- `dashboard/static/chat/stream.js`
- `dashboard/static/chat/composer.js`
- `tests/dashboard/test_chat_templates.py`

## Test Results

```
uv run pytest tests/dashboard/test_chat_templates.py -v
19 passed, 0 failed
```

Ruff: 1 pre-existing lint (SIM105) in `dashboard/routers/code.py:156` — not part of S03.

---

## Findings

### CRITICAL — 0

None.

---

### HIGH — 2

**H1: Slash menu has no blur handler**  
`composer.js:114–188` — The slash menu opens on `/` and closes on `Escape`, but there is no `blur` listener on the textarea to close the menu when focus leaves the input. A user who tabs away or clicks elsewhere will find the menu stuck open.

- Lines: `composer.js` input `blur` handler missing
- Spec: "closes on Esc or blur"

**H2: Context chip not re-synced after htmx swap**  
`composer.js:108–112` — `syncContextChip()` is called after htmx swaps `code-content-root`, but the new element rendered from the server has `data-module-path=""` (empty string). The chip is only created when `!existing` with a non-empty path, so after every swap the chip disappears and never returns until page reload.

- Lines: `composer.js:108–112`
- Spec: "auto-populated from `data-module-path` on load **and on htmx `afterSwap`**"

---

### MEDIUM — 5

**M1: No 900px responsive breakpoint**  
`project_code.html:87` — The grid uses `grid-template-columns: 1fr var(--chat-width)` unconditionally. Tailwind's `lg:` breakpoint (1024px) is used for the drawer, but the spec explicitly requires ≥900px. The chat panel will be visible beside the reading surface at ~950px viewports with no responsive collapse.

**M2: Slash menu missing `aria-activedescendant` / `aria-selected`**  
`composer.html:9–12` — The listbox has `role="listbox"` but:
- No `aria-activedescendant` on the textarea/input
- No `aria-selected` on the option items (`item.classList.add(...)` only adds styling classes, no ARIA)
- This fails the "keyboardable (↑/↓/Enter)" accessibility contract

**M3: No focus return after panel collapse**  
`panel.js:27–30` — `togglePanel()` changes `data-collapsed` and width but never moves focus. After collapsing, the focus stays wherever it was (e.g., inside the textarea), leaving keyboard users without orientation. Per spec, focus should return to `#chat-collapse-btn`.

**M4: Drawer has no focus trap**  
`panel.js:85–107` — `openDrawer()` / `closeDrawer()` toggle classes but do not implement focus trapping. A keyboard user can Tab outside the drawer while it is open. Per spec, "focus trapped while open".

**M5: Drawer close doesn't return focus to open button**  
`panel.js:103–107` — `Escape` closes the drawer but focus is not moved back to `#chat-drawer-open`. Per spec, "Esc closes and returns focus".

---

### LOW — 3

**L1: Stale `fragments/code_qa_panel.html` not deleted**  
The S03 report claims this file was deleted, but `dashboard/templates/fragments/code_qa_panel.html` still exists on disk (10953 bytes, last modified Apr 18). It is not referenced anywhere, so it is inert dead code, but the deletion claim in the report is inaccurate.

**L2: `.tap` CSS class unused**  
`chat.css:7` defines `.tap { min-height: 44px; min-width: 44px; }` but no element in any template uses `class="tap"`. The hit targets are handled via Tailwind utilities directly on elements.

**L3: Ruff lint in pre-existing file**  
`dashboard/routers/code.py:156` has a SIM105 suggestion (use `contextlib.suppress` instead of try/except/pass). This predates S03 and is not in any S03-touched file.

---

## Checklist Summary

| Category | Item | Status |
|----------|------|--------|
| Layout | 2-column grid with `var(--chat-width)` | PASS |
| Layout | Independent scroll containers | PASS |
| Layout | `code_qa_panel.html` deleted | **FAIL** (file still exists) |
| Layout | Drawer fallback <900px | PARTIAL (breakpoint is lg:1024px, not 900px) |
| Panel | Width localStorage, 320..480 clamp | PASS |
| Panel | Drag cleanup on mouseup | PASS |
| Panel | Cmd+\\ collapse toggle | PASS |
| Panel | `role="region"` + aria-label | PASS |
| Panel | `role="log"` + aria-live | PASS |
| Panel | Buttons ≥44×44 with focus rings | PASS |
| Composer | Enter=newline, Cmd+Enter=send | PASS |
| Composer | Slash menu keyboard nav | PARTIAL (no blur close, no aria-activedescendant) |
| Composer | Context chip auto-populated | PARTIAL (broken after htmx swap) |
| Composer | Image paste/drop/picker → chips | PASS |
| Composer | MIME validation + toast | PASS |
| Composer | 501 stub (no state clear) | PASS |
| Scroll | IntersectionObserver anchor | PARTIAL (observer only toggles btn visibility, no stickiness release) |
| Scroll | Scroll-to-bottom button | PASS |
| Scroll | First paint instant | PASS |
| Scroll | min-height: 50dvh last assistant | PASS |
| SSE | Parses `event:` + `data:` lines | PASS |
| SSE | b64 decode via atob+TextDecoder | PASS |
| SSE | `window.__iwChatCancel` abort | PASS |
| SSE | Delegates via callbacks (S05 TODOs) | PASS |
| SSE | No eval/innerHTML/script injection | PASS |
| Accessibility | Slash menu ARIA listbox | PARTIAL (missing aria-activedescendant/selected) |
| Accessibility | Image chip remove aria-label | PASS |
| Accessibility | Focus return on collapse | **FAIL** |
| Accessibility | Drawer focus trap | **FAIL** |
| Accessibility | Drawer Esc returns focus | **FAIL** |
| Hygiene | No CDN added | PASS |
| Hygiene | Vanilla JS only, no IIFE leakage | PASS |
| Hygiene | `window.iwChat` namespace | PASS |
| Hygiene | Ruff clean | PARTIAL (pre-existing SIM105) |
| Hygiene | Tests exist and pass | PASS (19 passed) |

---

## Verdict

**Code review of S03 is complete. 2 HIGH, 5 MEDIUM, 3 LOW findings. No CRITICAL blockers.**

The implementation is structurally sound and the 19 template smoke tests pass. The two HIGH findings (slash menu blur trap, context chip disappearing after htmx swap) represent real correctness issues that should be fixed before S05 (streaming renderer) is wired in. The medium findings are focus management and ARIA gaps that are accessibility-sensitive.

**blocking_next_step: false** — S05 (streaming renderer) can proceed, but H1 and H2 should be addressed in a follow-up patch before user-facing testing.

---

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00008",
  "completion_status": "complete",
  "reviewed_step": "S03",
  "findings": {"critical": 0, "high": 2, "medium": 5, "low": 3},
  "blocking_next_step": false,
  "notes": "HIGH: slash menu no blur handler + context chip not re-synced after htmx swap. MEDIUM: no 900px breakpoint, slash menu missing aria-activedescendant/selected, no focus return on collapse/drawer close. LOW: stale code_qa_panel.html on disk, unused .tap CSS class, pre-existing ruff lint."
}
```
