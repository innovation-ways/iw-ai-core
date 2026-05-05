# I-00065 S01 Frontend Implementation Report

## Work Item
**I-00065** — Code-view chat panel: "+ New" visible when collapsed and duplicates greeting

## Step
**S01 Frontend** — two small frontend defect fixes

---

## What Was Done

### Bug 1 — Hide "+ New" button when chat panel is collapsed

**File**: `dashboard/templates/chat/panel.html` (lines 1–6)

Added `#chat-panel[data-collapsed="true"] #chat-new-btn,` to the existing CSS selector list so the "+ New" button is `display: none` when the panel is in its collapsed rail state.

```diff
  #chat-panel[data-collapsed="true"] #chat-context-label,
  #chat-panel[data-collapsed="true"] #chat-messages,
  #chat-panel[data-collapsed="true"] #chat-scroll-to-bottom-wrap,
  #chat-panel[data-collapsed="true"] #chat-composer,
+ #chat-panel[data-collapsed="true"] #chat-new-btn,
  #chat-panel[data-collapsed="true"] #chat-collapse-btn { display: none; }
```

### Bug 2 — `showEmptyState` must not duplicate the greeting

**File**: `dashboard/static/chat/panel.js` (lines 175–182)

At the top of `showEmptyState`, added two lines that look up any pre-existing `#chat-empty-state` element and remove it before the rest of the function runs — preventing duplicate greeting blocks when "+ New" is clicked multiple times.

```javascript
function showEmptyState() {
    var messages = document.getElementById('chat-messages');
    if (!messages) return;
    // Remove any pre-existing empty-state block so clicking "+ New"
    // multiple times never stacks duplicate greetings.
    var existingEmpty = document.getElementById('chat-empty-state');
    if (existingEmpty) existingEmpty.remove();
    // Remove all article bubbles but keep the scroll anchor
    var articles = messages.querySelectorAll('article');
    ...
}
```

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/chat/panel.html` | Added `#chat-new-btn` to `[data-collapsed="true"]` hide selector |
| `dashboard/static/chat/panel.js` | Added pre-existing `#chat-empty-state` removal in `showEmptyState` |

---

## Preflight Checks

| Check | Result |
|-------|--------|
| `make format` | `panel.html` and `panel.js` — no changes needed; unrelated drift in other files reported (pre-existing, not introduced by this step) |
| `make typecheck` | **OK** — zero errors |
| `make lint` (incl. `node --check`) | `node --check` on `panel.js` — **OK** (no output = no errors); unrelated pre-existing lint errors in other files |

---

## Test Verification

Ran `make test-frontend` (alias of `make test-dashboard`):

```
429 passed, 10 skipped, 1 xfailed, 2 warnings in 35.33s
```

All dashboard tests pass. Zero failures introduced by this step.

---

## TDD Verification (RED/GREEN)

- **RED**: The bugs are confirmed by the design doc's "Test to Reproduce" section — pre-fix, `#chat-new-btn` is absent from the hide selector (would fail `test_i00065_new_button_hidden_when_collapsed`) and `showEmptyState` never removes `#chat-empty-state` before inserting (would fail `test_i00065_show_empty_state_removes_existing_before_insert`).
- **GREEN**: Both fixes applied — two CSS clauses added to the selector list; two JS lines added at top of `showEmptyState`.
- **REFACTOR**: No refactoring needed; fix is minimal by design.

---

## Blockers

None.

---

## Notes

- No new Tailwind classes introduced — `make css` was **not** required.
- No database migrations or Docker operations involved.
- JS edit strictly follows existing code style: `var`, semicolons, `function` keyword, no arrow functions.
- Lint failures in `make lint` output are pre-existing in unrelated worktrees/files — not introduced by these changes.
