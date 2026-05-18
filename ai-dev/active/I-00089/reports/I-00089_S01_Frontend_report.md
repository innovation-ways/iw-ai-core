# I-00089_S01_Frontend_report

## Step Summary

**Work Item**: I-00089 — AI Assistant panel in-header collapse button unusable in both states
**Step**: S01 — Frontend Implementation
**Agent**: frontend-impl

## What Was Done

Fixed both bugs in `dashboard/templates/chat_assistant/panel.html` and added supporting CSS in `dashboard/static/chat_assistant/chat.css`.

### Bug A — Hide collapse button when panel is collapsed

Extended the inline `<style>` block (line 12) to include `#chat-assistant-collapse-btn` in the `display: none` selector group for the collapsed state:

```css
#chat-assistant-panel[data-collapsed="true"] #chat-assistant-collapse-btn { display: none; }
```

This ensures the `<` button is not rendered/visible when `data-collapsed="true"`.

### Bug B — Give expanded-state collapse button visual weight

Modified the collapse button element (lines 66-73) to add:
- `title="Collapse panel"` — hover tooltip (exact attribute the regression test asserts)
- `class="… chat-assistant-collapse-btn-distinct"` — custom marker class
- `ml-1` — left margin for visual separation from the toggle-icon cluster
- `w-4 h-4` icon size (upgraded from `w-3.5 h-3.5`)

Preserved `aria-label="Collapse AI Assistant panel (Ctrl+/)"` exactly. No other attributes changed.

Added supporting CSS rule in `chat.css` (lines 254-261):

```css
/* ── Collapse button distinct affordance (I-00089) ── */
#chat-assistant-panel:not([data-collapsed="true"]) #chat-assistant-collapse-btn.chat-assistant-collapse-btn-distinct {
  border: 1px solid var(--border);
  background: var(--muted);
}
#chat-assistant-panel:not([data-collapsed="true"]) #chat-assistant-collapse-btn.chat-assistant-collapse-btn-distinct:hover {
  background: var(--muted-foreground);
  color: var(--background);
}
```

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/chat_assistant/panel.html` | Bug A: extended inline `<style>` display:none list; Bug B: added `title`, `chat-assistant-collapse-btn-distinct` class, `ml-1`, `w-4 h-4` to collapse button |
| `dashboard/static/chat_assistant/chat.css` | Added `chat-assistant-collapse-btn-distinct` CSS rule with border, background, and hover state |

## Preflight Checks

| Check | Result |
|-------|--------|
| `make format` | ok — no formatting drift |
| `make typecheck` | ok — no type errors (255 source files) |
| `make lint` | ok — all checks passed (includes `check_templates.py` for Jinja2) |

## Tests

- **Dashboard smoke test**: `uv run pytest tests/dashboard/ -k chat_assistant -v --no-cov` — 1 skipped (no existing chat_assistant tests match the filter), 0 failed
- **Template smoke test** (inline Python): skipped — `create_app()` requires DB context; the testclient approach needs full test infrastructure (blocked by LiveDBGuard in worktree)
- **Note**: `tests/dashboard/test_chat_assistant_header.py` (reproduction tests for AC1/AC2) is written in S03, not S01

## Notes

- Chose the `chat-assistant-collapse-btn-distinct` custom class marker over the Tailwind `border-l` path — the custom class provides a cleaner visual separation (muted background + border) without relying on `make css` in the worktree
- No JS changes were made — `chat.js:953-956` click handler is correct and works for both states once the button is visible/hidden properly
- The `aria-label` was preserved exactly; only `title` was added for hover tooltip
- Plain CSS appended to `chat.css` is served as-is per the I-00067 fallback policy, no `make css` required