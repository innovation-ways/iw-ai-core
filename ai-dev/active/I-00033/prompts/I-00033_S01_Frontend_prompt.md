# I-00033_S01_Frontend_prompt

**Work Item**: I-00033 — Code view layout bugs: undismissible "Last run" banner, misplaced scrollbar, wasted space on chat collapse
**Step**: S01
**Agent**: frontend-impl

---

## Input Files

- `ai-dev/active/I-00033/I-00033_Issue_Design.md` — Design document (read this first, especially Root Cause Analysis)
- `ai-dev/active/I-00033/evidences/pre/I-00033-code-view-initial.png` — pre-fix screenshot
- `dashboard/templates/fragments/code_job_report.html` — "Last run" banner fragment
- `dashboard/templates/project_code.html` — Code page grid layout
- `dashboard/templates/fragments/code_architecture_view.html` — Architecture card (scroll target)
- `dashboard/static/chat/panel.js` — chat panel collapse/resize logic
- `dashboard/templates/chat/panel.html` — chat panel markup
- `dashboard/routers/code_ui.py` — context vars passed to the templates (`last_completed_job`, `last_completed_recent`, `current_project`) — read-only reference
- `dashboard/CLAUDE.md` — dashboard conventions (htmx patterns, no dynamic Tailwind classes)

## Output Files

- Modified: `dashboard/templates/fragments/code_job_report.html`
- Modified: `dashboard/templates/project_code.html`
- Modified: `dashboard/templates/fragments/code_architecture_view.html`
- Modified: `dashboard/static/chat/panel.js`
- Modified: `dashboard/templates/chat/panel.html`
- (Optional) Created: `dashboard/static/code/last_run_banner.js` — only if the dismissal script grows past ~20 lines
- Report: `ai-dev/active/I-00033/reports/I-00033_S01_Frontend_report.md`

## Context

The project Code view (`/project/{id}/code`) has three desktop-only layout bugs bundled into this one incident because they share files and a single verification environment. Read the design document's "Root Cause Analysis" section before writing code. All three fixes are pure frontend (Jinja templates + client JS + literal Tailwind classes). No router, no service, no database, no migration.

## Requirements

### Bug 1 — Dismissible "Last run" banner

**Current markup** (`dashboard/templates/fragments/code_job_report.html`): a `div` with the banner text and a "View →" link. No close affordance, no client-side state.

**Change**:

1. Add a close button after the "View →" link. Use an `×` icon (SVG, matching the existing SVG style in the file — 3.5 w/h, `stroke="currentColor"`). The button MUST carry:
   - `type="button"`
   - `aria-label="Dismiss last-run banner"`
   - `data-dismiss-job-id="{{ last_completed_job.id }}"`
   - `data-project-id="{{ current_project.id }}"`
   - Tailwind classes for placement and hover state — all classes must be literal strings, no dynamic construction.
2. Add an inline `<script>` at the bottom of the fragment (inside the outermost `<div>`) that:
   - On load (and on htmx `htmx:afterSettle` if the banner is swapped in dynamically), reads `localStorage.getItem('iw_code_lastrun_dismissed:' + projectId)` where `projectId` comes from the button's `data-project-id`.
   - If the stored value equals the current `data-dismiss-job-id`, sets `display: none` on the banner's root div.
   - On click of the close button, writes `localStorage.setItem('iw_code_lastrun_dismissed:' + projectId, jobId)` and hides the banner.
3. The banner root div needs an `id` the script can reference — use `id="code-last-run-banner"`.

**Key properties (tested by S03)**:

- The rendered HTML MUST contain the exact literal `data-dismiss-job-id="{{ job.id }}"` (with the resolved id).
- The localStorage key MUST be scoped by project id: `iw_code_lastrun_dismissed:<project_id>`. This prevents one project's dismissal leaking to another.
- Dismissal is per-job-id: when a NEW job completes (different id), the banner reappears automatically because the stored id no longer matches.

**If the inline script grows past ~20 lines**, extract to `dashboard/static/code/last_run_banner.js` and include it via `<script src="/static/code/last_run_banner.js" defer></script>` in `project_code.html` (add it next to the existing chat script includes at the bottom of the `{% block content %}`). Prefer inline for brevity.

### Bug 2 — Move scroll container from outer column to Architecture card

**Current markup**:

- `project_code.html:89-90` — `<div id="code-content-root" class="lg:overflow-y-auto lg:pr-4" ...>`
- `code_architecture_view.html:1` — `<div class="bg-card border border-border rounded-lg overflow-hidden">` (the card root)

**Change**:

1. In `project_code.html`, remove `lg:overflow-y-auto` and `lg:pr-4` from `#code-content-root`. Keep the other classes and all `data-*` attributes untouched. The parent grid `#page-body` already has `lg:h-[calc(100vh-12rem)]` — keep that.
2. Also in `project_code.html`, add `lg:gap-4` to `#page-body` (currently `grid gap-0 grid-cols-1 lg:grid-cols-[1fr_var(--chat-width)] lg:h-[calc(100vh-12rem)]`). This gives the visible gutter between text and chat columns. Change `gap-0` to `gap-0 lg:gap-4` — keep mobile gap at 0.
3. In `code_architecture_view.html`, change the root card `<div>`'s classes from `bg-card border border-border rounded-lg overflow-hidden` to `bg-card border border-border rounded-lg h-full overflow-y-auto`. **Remove** `overflow-hidden` — do not leave both `overflow-hidden` and `overflow-y-auto` on the same element (they conflict and the final-class order is fragile). Horizontal bleed is already handled by the `.prose-doc` child rules (`pre` has `overflow-x: auto`, `img` has `max-width: 100%`), so `overflow-x: visible` on the card root is safe.

**Key properties (tested by S03)**:

- `#code-content-root` MUST NOT contain `overflow-y-auto` after the change.
- The Architecture card root MUST contain both `overflow-y-auto` and `h-full`. Without `h-full`, no scrollbar appears because the card grows to fit content (there is no definite height for `overflow-y-auto` to bound against).
- On desktop, the scrollbar visually sits inside the card's right border with a visible gap (the `lg:gap-4`) to the chat panel.

**Do not** change the `#code-components-section` or `#code-detail-panel` divs — they stay inside the scroll container.

### Bug 3 — Toggle `--chat-width` on chat collapse/expand

**Current JS** (`dashboard/static/chat/panel.js:17-27`):

```javascript
function applyCollapsedState(collapsed) {
  if (!panel) return;
  panel.dataset.collapsed = collapsed;
  if (collapsed) {
    panel.style.width = '48px';
    if (collapseBtn) collapseBtn.setAttribute('aria-label', 'Expand chat panel (Cmd+\\)');
  } else {
    panel.style.width = '';
    if (collapseBtn) collapseBtn.setAttribute('aria-label', 'Collapse chat panel (Cmd+\\)');
  }
}
```

**Change**:

1. In `applyCollapsedState(collapsed)`:
   - On collapse: set `document.documentElement.style.setProperty('--chat-width', '48px')`. Keep the `panel.style.width = '48px'` line (belt-and-braces — if CSS variable is cleared or the panel is used in a non-grid context elsewhere, the inline width still takes effect).
   - On expand: set `document.documentElement.style.setProperty('--chat-width', chatWidth + 'px')` (the module-scoped `chatWidth` already holds the persisted width, clamped to 320..480).
2. Boot order: the existing `document.documentElement.style.setProperty('--chat-width', chatWidth + 'px')` at line 11 is unchanged. The new `applyCollapsedState(false)` call at line 112 will re-assert `--chat-width = chatWidth + 'px'` — no-op on first boot, but correct.
3. Make sure the resize handle (`mousemove` handler at lines 95-101) still works: it writes `--chat-width` directly, which is the correct source of truth. Confirm no conflict.

**Key properties (tested by S03)**:

- After `applyCollapsedState(true)`, `getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim()` MUST equal `"48px"`.
- After `applyCollapsedState(false)`, `--chat-width` MUST equal the saved `chatWidth` (default 400, within 320..480).
- The resize handle still writes `--chat-width` and persists to `localStorage.iw_chat_width` on mouseup — no change in that path.

### Bug 3 (companion) — Collapsed-rail CSS in `chat/panel.html`

When the panel is collapsed (`data-collapsed="true"`), the chat header, message list, scroll-to-bottom button, and composer should hide so only the collapse/expand button is visible inside the 48px rail. Today the header's context label truncates awkwardly at 48px.

**Change**:

1. Add an inline `<style>` at the top of `chat/panel.html` (the panel markup already has `data-collapsed="false"` on its root). The style block targets `#chat-panel[data-collapsed="true"]`:
   ```html
   <style>
     #chat-panel[data-collapsed="true"] #chat-context-label,
     #chat-panel[data-collapsed="true"] #chat-messages,
     #chat-panel[data-collapsed="true"] #chat-scroll-to-bottom-wrap,
     #chat-panel[data-collapsed="true"] .chat-composer { display: none; }
     #chat-panel[data-collapsed="true"] #chat-collapse-btn svg { transform: rotate(180deg); }
   </style>
   ```
   The composer is rendered by the `{% include "chat/composer.html" %}` at line 42 — if it does not have a `.chat-composer` class today, adjust the selector to match whatever class/id wraps the composer in that partial (read the file to confirm). If no stable selector exists, add a `class="chat-composer"` wrapper in `panel.html` around the include.
2. Keep `#chat-collapse-btn` visible (no display:none). The button's SVG arrow rotates 180° in the collapsed state so it points outward (indicating "expand").

**Key properties (tested visually in S11)**:

- At 48px panel width, only the collapse button is visible.
- Clicking the button expands the panel; the arrow rotates back.
- No content overflows the 48px rail at any time during the transition.

### No dynamic Tailwind classes

**CRITICAL**: Every Tailwind class you add must be a literal string in the template or JS. Do NOT build class names from variables:

- BAD: `class="w-{{ width }}px"` (the CDN has no JIT — this class won't exist)
- BAD: ```js el.className = 'mt-' + size``` (same reason)
- GOOD: inline `style="width: 48px"` for dynamic values, or a literal class with a CSS rule.

This matches the existing codebase — no dynamic classes anywhere in `dashboard/`.

## Project Conventions

Read `dashboard/CLAUDE.md`. In particular:

- **No build step** — Tailwind is loaded from CDN. No purge, no JIT for unseen class names.
- **Templates in `fragments/` MUST NOT extend `base.html`** — `code_job_report.html` and `code_architecture_view.html` are fragments; do not add `{% extends %}`.
- **Routes are thin** — do not touch `dashboard/routers/code_ui.py` for this incident. The banner's existence is already gated by `last_completed_recent` (1h window) server-side; dismissal is purely client-side.
- **htmx-aware** — the banner may be re-rendered by htmx on job completion (via `hx-target="#code-status-panel" hx-swap="innerHTML"` in the dropdown buttons). The dismissal script MUST re-run after swap. Listen for `htmx:afterSettle` on `#code-status-panel` or on `document.body` filtered by the target id.

## Playwright CLI rules (from root CLAUDE.md)

Not needed for this step (you are writing code, not running browsers). S11 and S03's Playwright test will verify at runtime. Do NOT `npx playwright install` or modify `.playwright/cli.config.json`.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: S03 writes the reproduction tests. You can preview the assertions in the design doc's "Test to Reproduce" section — structure your changes so they satisfy those assertions literally.
2. **GREEN**: Implement the three fixes above. Verify by hand:
   - Run the dashboard locally: `make dashboard-start`
   - Open `http://localhost:9900/project/iw-ai-core/code`
   - Click the close button on the banner, reload — banner stays hidden.
   - Scroll the text — scrollbar is inside the card.
   - Click collapse — text column grows, panel shrinks to 48px rail.
3. **REFACTOR**: Only if the dismissal script exceeds ~20 lines — extract to `dashboard/static/code/last_run_banner.js`. Otherwise keep inline.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make lint` — ruff + JS syntax check on dashboard/static/**/*.js. Must be clean.
2. Run `uv run ruff format --check .` — clean.
3. Manually verify in a browser (or describe in your report why you could not — e.g., dashboard not running). Verify each of the three bugs is fixed.
4. Do **NOT** report `tests_passed: true` unless `make lint` and `uv run ruff format --check .` exit 0.

Note: the reproduction tests land in S03. S01's success criterion is "all three fixes compile, templates render without Jinja errors, and manual smoke confirms each bug is fixed."

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00033",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/code_job_report.html",
    "dashboard/templates/project_code.html",
    "dashboard/templates/fragments/code_architecture_view.html",
    "dashboard/static/chat/panel.js",
    "dashboard/templates/chat/panel.html"
  ],
  "tests_passed": true,
  "test_summary": "make lint clean; ruff format clean; manual smoke in browser confirms all 3 bugs fixed",
  "blockers": [],
  "notes": "Document: (a) whether you extracted the dismissal script to a .js file or kept inline; (b) which approach you chose for the Architecture card scroll (overflow-hidden + overflow-y-auto, or removed overflow-hidden); (c) whether the composer had a stable class/id for the collapsed-rail CSS."
}
```

- If any of the three bugs cannot be fixed as specified (e.g., a CSS variable approach fails in a real browser), set `completion_status: blocked` and describe the blocker — do not improvise a different solution silently.
