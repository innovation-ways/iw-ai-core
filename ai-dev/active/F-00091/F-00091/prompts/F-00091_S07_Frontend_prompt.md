# F-00091_S07_Frontend_prompt

**Work Item**: F-00091 -- AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar
**Step**: S07
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy. This step touches no Docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step adds no migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00091 --json`
- `ai-dev/active/F-00091/F-00091_Feature_Design.md` — Design (read Scope → S07, AC3, AC4, Invariant 3, and Frontend Changes)
- `ai-dev/active/F-00091/evidences/pre/F-00091-before-02-project-iw-ai-core.png` — Current state: no visible context indicator near Send/Abort/Clear
- `dashboard/templates/chat_assistant/composer.html:32-35` — Current `<span id="chat-assistant-context-pct">` text badge
- `dashboard/static/chat_assistant/chat.js:1864-1897` — Current `_applyContextPct` and `_refreshContextPct`
- `dashboard/static/chat_assistant/chat.css:448-469` — Current context-pct CSS
- S06 report: `ai-dev/work/F-00091/reports/F-00091_S06_Backend_report.md` — Confirms payload shape

## Output Files

- `ai-dev/work/F-00091/reports/F-00091_S07_Frontend_report.md`

## Context

Replace the tiny hidden-by-default text badge with a small inline progress bar (~60px × 5px) followed by a numeric percentage. Always visible while a tab is active. Three visual states: known (green/amber/red by threshold), unknown_window (greyed), unknown_runtime (greyed with a different tooltip).

Read **Scope → S07**, **AC3**, **AC4**, **Invariant 3**, and **Frontend Changes** before touching code.

## Requirements

### 1. Replace markup in `composer.html`

In `dashboard/templates/chat_assistant/composer.html`, replace the existing `<span id="chat-assistant-context-pct" …></span>` with:

```html
<div id="chat-assistant-context-pct"
     class="chat-assistant-context-pct chat-assistant-context-pct--unknown"
     role="status"
     aria-label="Context window usage"
     title="Context window usage">
  <span class="chat-assistant-context-pct__bar" aria-hidden="true">
    <span class="chat-assistant-context-pct__fill" style="width: 0%;"></span>
  </span>
  <span class="chat-assistant-context-pct__label">—%</span>
</div>
```

- KEEP the id `chat-assistant-context-pct` so existing JS hooks still find the element.
- The element MUST NOT carry the `hidden` Tailwind class anymore. Per Invariant 3, it is NEVER hidden while a tab is active.
- The element ships in the unknown state — once `_applyContextPct` runs it flips to the appropriate state.

### 2. CSS in `chat_assistant/chat.css`

Replace the existing `.chat-assistant-context-pct` block. New rules:

```css
.chat-assistant-context-pct {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.7rem;
  color: var(--muted-foreground);
  white-space: nowrap;
}

.chat-assistant-context-pct__bar {
  display: inline-block;
  width: 60px;
  height: 5px;
  background: var(--muted);
  border-radius: 2px;
  overflow: hidden;
  position: relative;
}

.chat-assistant-context-pct__fill {
  display: block;
  height: 100%;
  background: #16a34a;            /* green-600 */
  transition: width 250ms ease;
}

.chat-assistant-context-pct.is-warn  .chat-assistant-context-pct__fill { background: #d97706; } /* amber-600 */
.chat-assistant-context-pct.is-crit  .chat-assistant-context-pct__fill { background: var(--destructive); }

.chat-assistant-context-pct--unknown .chat-assistant-context-pct__fill {
  background: repeating-linear-gradient(
    45deg, var(--muted) 0 4px, var(--border) 4px 8px
  );
  width: 100% !important;          /* full-width stripe so it's visibly "unknown" */
  opacity: 0.5;
}

.chat-assistant-context-pct--unknown .chat-assistant-context-pct__label {
  color: var(--muted-foreground);
  font-style: italic;
}

@media (prefers-color-scheme: dark) {
  .chat-assistant-context-pct.is-warn .chat-assistant-context-pct__fill { background: #fbbf24; }
}
```

Append to `chat.css` (not `styles.css`). Per CLAUDE.md, plain CSS files are served as-is.

### 3. JS rewrite of `_applyContextPct` and `_refreshContextPct`

In `dashboard/static/chat_assistant/chat.js`:

- `_applyContextPct(payload)` now takes the WHOLE shape `{ pct, used_tokens, window_tokens, status, reason }`, not just a number. Cases:
  - `status === "known"` AND `pct` is a finite number → set fill width to `Math.min(100, Math.max(0, pct))%`, set label to `Math.round(pct) + '%'`, set tooltip to `usedK + ' / ' + windowK + ' tokens (' + Math.round(pct) + '%)'` where `usedK`/`windowK` is the human-formatted count (e.g., "120k", "200k"). Apply `is-warn` at 70–89%, `is-crit` at 90+%. Remove `--unknown`.
  - `status === "unknown_window"` or `status === "unknown_runtime"` → add `--unknown` class, set label to `—%`, set tooltip to `reason` (fall back to a generic message if `reason` is missing).
- `_refreshContextPct(tabId)`:
  - Continue to fetch `/api/chat/tabs/<id>` every 5s while a tab is active.
  - Pass the new payload to `_applyContextPct`. Read `data.session.context_pct_status`, `data.session.context_pct`, `data.session.used_tokens`, `data.session.window_tokens`, `data.session.context_pct_reason`.
  - On fetch failure: pass `{ status: 'unknown_runtime', reason: 'Could not contact runtime' }`. Do NOT hide the element.
- When the active tab is null (no tab selected): hide the element via setting `display: none`. This is the ONLY allowed `display: none` case for this element — when there is no active tab, there is nothing to show.
- Search the file for every existing call to `_applyContextPct(...)`. Each currently passes a bare `pct` number. Update each call site to pass the full payload (or wrap legacy callers in a small adapter that synthesises the new shape).

### 4. Token formatting helper

Add `_formatTokenCount(n)` that returns "120k" for 120000, "1.2M" for 1200000, etc. Mirror the convention already used elsewhere in the project; if no helper exists in `chat.js` already, add a small one in the same IIFE.

### 5. TDD

Add `tests/dashboard/test_context_pct_progress_bar.py`:

- A JSDOM/regex-style test asserting the served `composer.html` contains the new markup (`.chat-assistant-context-pct__bar`, `.chat-assistant-context-pct__fill`, the role and aria-label).
- A test asserting the served `chat.js` no longer contains the old text-only mutation pattern (`el.textContent = rounded + '%'` is fine; the test should look for the new shape via the helper class names).

Capture RED → GREEN.

### 6. Do NOT touch

- The server payload (S06 owns that).
- The Tailwind config or `styles.css` regenerated output.
- Other UI components in the panel.

## Project Conventions

Read `dashboard/CLAUDE.md`. Specifically:

- Tailwind classes that aren't already in `styles.css` will silently not apply — use the existing variables (`var(--muted)`, `var(--destructive)`) or append plain CSS to `chat.css`.
- Match the chat.js ES5 IIFE idiom.
- Keep the element role/aria for screen-reader accessibility.

## TDD Requirement

Standard RED → GREEN → REFACTOR. Record RED in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint` (includes the template check)

## Test Verification (NON-NEGOTIABLE)

Run only the test file you wrote:

```bash
uv run pytest tests/dashboard/test_context_pct_progress_bar.py -v
```

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "frontend-impl",
  "work_item": "F-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat_assistant/composer.html",
    "dashboard/static/chat_assistant/chat.css",
    "dashboard/static/chat_assistant/chat.js",
    "tests/dashboard/test_context_pct_progress_bar.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_context_pct_progress_bar.py::test_bar_markup_present — AssertionError: '.chat-assistant-context-pct__bar' not found in composer.html",
  "blockers": [],
  "notes": ""
}
```
