# I-00057_S02_CodeReview_Frontend_prompt

**Work Item**: I-00057 -- Chat panel collapse toggle is intrusive and panel starts open
**Step Being Reviewed**: S01 (Frontend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status I-00057 --json`
- `ai-dev/active/I-00057/I-00057_Issue_Design.md`
- `ai-dev/active/I-00057/reports/I-00057_S01_Frontend_report.md`
- All files in S01's `files_changed`

## Output Files

- `ai-dev/active/I-00057/reports/I-00057_S02_CodeReview_report.md`

## Pre-Review Gate

```bash
make lint     # also runs node --check on dashboard JS
make format
```

NEW violations on changed files → CRITICAL.

## Review Checklist

### 1. Floating tab fully removed

- `#chat-toggle-tab` no longer appears in `dashboard/templates/chat/panel.html` — neither the element nor any styles referencing it.
- The literal substring `style="left: -48px;"` is absent from the template.
- `panel.js` does NOT reference `chat-toggle-tab` anymore (no `getElementById('chat-toggle-tab')`, no listener).
- `dashboard/static/chat.css` no longer contains rules keyed on `#chat-toggle-tab` (the original lines 11-27 block is gone). Run `grep -n chat-toggle-tab dashboard/static/chat.css dashboard/static/styles.css dashboard/templates/chat/panel.html dashboard/static/chat/panel.js` and confirm zero hits.

### 2. Default collapsed state

- The template ships with `data-collapsed="true"` on `#chat-panel`.
- `panel.js` reads `localStorage.getItem('iw_chat_collapsed')`. When the value is `null`, the initial collapsed state is `true`. When the value is `'true'` or `'false'`, it is honored.
- The initial state is applied via `applyCollapsedState(initialCollapsed)` early enough that the user does not see a flash of the wrong state. (If a flash is unavoidable due to script ordering, the template's `data-collapsed="true"` default keeps the worst case as "starts collapsed even when user wanted expanded" — acceptable.)

### 3. Persistence

- `togglePanel()` persists the new state via `localStorage.setItem('iw_chat_collapsed', String(next))`.
- The Cmd+\\ keyboard shortcut goes through `togglePanel()` and therefore inherits persistence. Verify by reading the shortcut handler.
- `try/catch` around `setItem` (or equivalent) so a Safari private-mode QuotaExceededError doesn't break the toggle.

### 4. Two-mode panel layout

- Expanded mode shows: header (title + collapse chevron), messages, scroll-to-bottom, composer.
- Collapsed mode shows: rail (chat icon + rotated "Chat" label + expand button) ONLY. No leak of header or messages content.
- CSS rules cleanly toggle between the two. No `display: none` applied via JS — purely CSS-driven keyed on `[data-collapsed]`.
- The collapsed-rail click target (`#chat-expand-rail`) is a `<button>` (or has `role="button"` + keyboard handlers).

### 5. Accessibility

- Both controls have `aria-label` describing the action ("Collapse chat panel (Cmd+\\)" / "Expand chat panel (Cmd+\\)").
- Tab order is sensible — when collapsed, the only focusable target inside the panel is the expand button.
- The mobile drawer logic still works — `#chat-drawer-open`, `#chat-drawer-backdrop` are unchanged.

### 6. CLAUDE.md conformance

- No dynamic Tailwind class construction.
- `make css` was run if new classes appear (check `dashboard/static/styles.css` diff).
- No `console.log` debug statements left in `panel.js`.
- The template still does NOT extend `base.html`.

## Test Verification

```bash
make test-unit
```

## Severity Levels

| CRITICAL | Floating tab still present; data-collapsed wrong; persistence broken | Must fix |
| HIGH | Two-mode layout leaks (e.g. composer visible when collapsed); accessibility missing label | Must fix |
| MEDIUM (fixable) | Class drift, unused CSS rule | Should fix |
| MEDIUM (suggestion) | Optional improvement | Author decides |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00057",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
