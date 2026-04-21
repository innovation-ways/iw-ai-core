# I-00033 S01 Frontend Report

## Summary

All three bugs fixed in `dashboard/` — pure frontend (Jinja templates + client JS + literal Tailwind classes). No router, service, database, or migration changes.

---

## Bug 1 — Dismissible "Last run" banner

**Files changed**: `dashboard/templates/fragments/code_job_report.html`, `dashboard/templates/project_code.html`, `dashboard/static/code/last_run_banner.js` (created)

**What was done**:
- Added `id="code-last-run-banner"` to the banner root div
- Added a close button (`×` SVG, 3.5×3.5, `stroke="currentColor"`) with `type="button"`, `aria-label="Dismiss last-run banner"`, `data-dismiss-job-id="{{ last_completed_job.id }}"`, and `data-project-id="{{ current_project.id }}"`
- Extracted the dismissal script to `dashboard/static/code/last_run_banner.js` (24 lines — exceeded ~20-line threshold)
- Added `<script src="/static/code/last_run_banner.js" defer>` to `project_code.html` alongside existing chat script includes

**Key properties satisfied**:
- `data-dismiss-job-id="<job_id>"` renders with the resolved job id (not a literal string)
- localStorage key is scoped by project id: `iw_code_lastrun_dismissed:<project_id>`
- Dismissal is per-job-id (new job id ≠ stored id → banner reappears)
- Script re-runs on `htmx:afterSettle` targeting `#code-status-panel` so htmx-swapped banners are also handled

---

## Bug 2 — Move scroll container from outer column to Architecture card

**Files changed**: `dashboard/templates/project_code.html`, `dashboard/templates/fragments/code_architecture_view.html`

**What was done**:
- `project_code.html:87-88`: Changed `#page-body` class from `grid gap-0 ...` to `grid gap-0 lg:gap-4 ...` (mobile gap stays 0; desktop gets 4-unit gutter between text and chat columns)
- `project_code.html:89-90`: Removed `lg:overflow-y-auto` and `lg:pr-4` from `#code-content-root`; kept all `data-*` attributes and other classes
- `code_architecture_view.html:1`: Changed root card class from `bg-card border border-border rounded-lg overflow-hidden` to `bg-card border border-border rounded-lg h-full overflow-y-auto` — removed `overflow-hidden` (conflicts with `overflow-y-auto`), added `h-full` (gives the scroll container a definite height so the scrollbar actually appears)

**Approach chosen**: Removed `overflow-hidden` rather than stacking both — avoids CSS conflict and fragile class ordering.

**Key properties satisfied**:
- `#code-content-root` no longer has `overflow-y-auto`
- Architecture card root has `h-full` + `overflow-y-auto` (definite height for scrollbar)
- `overflow-hidden` is not present on the card root (would conflict with `overflow-y-auto`)
- Horizontal bleed safe: `.prose-doc` children handle `overflow-x: auto` and `max-width: 100%`

---

## Bug 3 — Toggle `--chat-width` on chat collapse/expand

**Files changed**: `dashboard/static/chat/panel.js`, `dashboard/templates/chat/panel.html`

**What was done**:
- `panel.js:17-29`: `applyCollapsedState(collapsed)` now calls `document.documentElement.style.setProperty('--chat-width', collapsed ? '48px' : chatWidth + 'px')` on both collapse and expand; kept `panel.style.width = '48px'` belt-and-braces
- `chat/panel.html:1-7`: Added inline `<style>` targeting `#chat-panel[data-collapsed="true"]` to hide `#chat-context-label`, `#chat-messages`, `#chat-scroll-to-bottom-wrap`, and `#chat-composer`; rotates `#chat-collapse-btn svg` 180° via `transform: rotate(180deg)`

**Key properties satisfied**:
- After `applyCollapsedState(true)`: `getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim()` equals `"48px"`
- After `applyCollapsedState(false)`: `--chat-width` equals saved `chatWidth` (within 320..480)
- Resize handle (`mousemove` handler, lines 95-101) continues to write `--chat-width` directly — no conflict with `applyCollapsedState`
- Only collapse button visible at 48px panel width; arrow rotates outward

---

## Test Results

| Check | Result |
|-------|--------|
| `make lint` (ruff + JS syntax) | PASS |
| `uv run ruff format --check .` | PASS (246 files already formatted) |

---

## Notes

**(a) Extraction of dismissal script**: Extracted to `dashboard/static/code/last_run_banner.js` — the inline script grew to ~24 lines (exceeding the ~20-line threshold). The script is loaded via `<script src="/static/code/last_run_banner.js" defer>` in `project_code.html`, deferred so it does not block page render.

**(b) Architecture card scroll approach**: Chose to remove `overflow-hidden` and add `h-full overflow-y-auto` to the card root, rather than stacking both overflow declarations. This avoids the CSS conflict where `overflow-hidden` and `overflow-y-auto` on the same element have ordering-dependent behavior.

**(c) Composer selector for collapsed-rail CSS**: The composer form in `chat/composer.html` has `id="chat-composer"`, so the collapsed-rail CSS uses `#chat-panel[data-collapsed="true"] #chat-composer { display: none; }` as its selector — no wrapper class needed.