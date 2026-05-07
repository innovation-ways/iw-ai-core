# F-00079_S06_Frontend_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Step**: S06
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy. Browser automation goes through `playwright-cli` exclusively (used in S09 / S19 only — not in this step). Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Migration was added in S01. Do not touch alembic.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00079 --json`
- `ai-dev/active/F-00079/F-00079_Feature_Design.md`
- Reports from S01, S03, S05
- `dashboard/templates/pages/project/item_detail.html` — current tab bar (Artifacts button at line ~58)
- `dashboard/templates/fragments/item_artifacts.html` — file to delete
- `dashboard/templates/components/libs/` — sibling lib includes (Highlight.js, DOMPurify, Mermaid, etc.)
- `dashboard/static/styles.css` — append plain CSS rules here if Tailwind CLI fails (per `CLAUDE.md`)

## Output Files

- New: `dashboard/templates/fragments/item_files.html`
- New: `dashboard/templates/fragments/item_files_untracked.html` (untracked sub-panel, reusing `/artifact-raw` preview)
- New: `dashboard/templates/components/libs/diff2html.html` (vendored CSS + JS includes from `dashboard/static/vendor/diff2html/`, NO CDN)
- New: `dashboard/static/vendor/diff2html/` (vendored diff2html-ui slim bundle: CSS + JS files committed to the repo)
- New: `dashboard/static/files.js` (tree expand, filter, client-side per-file collapse toggle, dark-mode color-scheme sync)
- Modified: `dashboard/templates/pages/project/item_detail.html` (tab button swap)
- Modified: `dashboard/static/styles.css` (status-badge variants, +N −M bar, sticky headers if needed)
- Deleted: `dashboard/templates/fragments/item_artifacts.html`
- `ai-dev/active/F-00079/reports/F-00079_S06_Frontend_report.md`

## Context

You are building the Files tab UI for **F-00079**. The tab shell, the per-file diff cards, the untracked sub-panel, and the supporting JS/CSS. The tab uses **diff2html-ui** (slim bundle) loaded via the conventional libs include for client-side diff rendering. Read the design document's `Functional Requirements` (especially the `Files tab UI` and `Untracked artifacts sub-panel` sections), `Boundary Behavior`, and `Invariants` 8 (single source of truth for generated-file globs).

## Requirements

### 1. `dashboard/templates/components/libs/diff2html.html` and `dashboard/static/vendor/diff2html/`

**Vendored only — no CDN.** This matches the repo convention (Highlight.js, DOMPurify, Mermaid are all vendored under `dashboard/templates/components/libs/`) and is required for offline / air-gapped operation.

1. Download the diff2html-ui slim bundle for a pinned version (e.g., `diff2html@3.4.x`):
   - `diff2html.min.css`
   - `diff2html-ui-slim.min.js` (the slim variant; bundles highlight.js for common languages, ~100 KB gzipped)
2. Commit both files under `dashboard/static/vendor/diff2html/<version>/`. Include the upstream LICENSE file alongside (MIT) for attribution.
3. `dashboard/templates/components/libs/diff2html.html` is a small partial that emits the corresponding `<link rel="stylesheet" href="/static/vendor/diff2html/<version>/diff2html.min.css">` and `<script src="/static/vendor/diff2html/<version>/diff2html-ui-slim.min.js"></script>` tags. Mirror the existing libs-include pattern.

Do NOT reference jsDelivr, unpkg, or any other CDN.

### 2. `dashboard/templates/fragments/item_files.html`

Tab shell. NOT extending `base.html`. Layout:

- Top toolbar:
  - Step selector (`<select>` with `name="step"`) populated from `step_options` context list. Default option `value="all"` labelled "All steps (aggregate)".
  - Filter input (`<input type="text" placeholder="Filter files…">`).
  - Aggregate counts: `<span class="text-green-600">+{aggregate_added}</span>`, `<span class="text-red-600">−{aggregate_removed}</span>`, file count.
  - "Export PDF" link/button to `GET /project/{project_id}/item/{item_id}/files/export.pdf?step={current_step}`.
- Two-column layout (left: nested file tree using collapsible `<details>` elements; right: stacked diff cards). Each file row in the tree:
  - Status badge (A green / M amber / D red / R blue) — color **and** letter (WCAG 1.4.1).
  - Path (truncated with title attribute).
  - `+N −M` text + a proportional bar (CSS-only, e.g., `<div class="diff-bar"><span class="add" style="width:Xpx"></span><span class="del" style="width:Ypx"></span></div>`).
  - Generated badge if `is_generated`.
- Per-file diff cards:
  - Mounted as `<div class="diff-card" data-path="..." data-status="..." data-collapsed="..." data-large="..."></div>`.
  - Sticky filename header.
  - For files marked `data-large="true"` (≥500 lines), the card starts collapsed with a "Show diff" toggle. **Expansion is purely client-side** — toggle a CSS class on the card; the diff text is already in the DOM (`Diff2HtmlUI` renders the entire aggregate response on initial fetch). No server roundtrip per file.
  - For files ≥5000 lines or binary, render a placeholder + "Download raw diff" link (the link points at `/files/diff?step=<current>` so the browser saves the full diff; users can search/grep externally).
- "Other worktree files" sub-panel:
  - Collapsed by default `<details>` element, rendered ONLY when `worktree_alive` is true.
  - On expand, htmx fetches `/files/untracked`, populates the file list, and reuses the existing `/artifact-raw` preview pattern from the deleted Artifacts tab.
- Initial diff text is fetched client-side via `fetch('/files/diff?step=all')` after the page loads, then handed to `Diff2HtmlUI` for rendering. The toolbar dropdown change re-fetches with the new `step` value and re-renders.

### 3. `dashboard/templates/fragments/item_files_untracked.html`

Reuses the markdown / image / text preview behaviour from the deleted `item_artifacts.html`. Two-pane: left = list of untracked files, right = preview area that loads from `/artifact-raw?path=...` on click. Hidden entirely on archived items (the `worktree_alive` flag is False).

### 4. `dashboard/static/files.js`

Small client-side module (vanilla JS, no build step). Responsibilities:

- On tab fragment load: fetch raw diff, instantiate `Diff2HtmlUI`, attach to a mount element.
- Toolbar step dropdown change: re-fetch and re-render.
- Filter input: live-filter tree rows and diff cards by path substring; update aggregate counters to reflect filtered scope.
- Tree node click: scroll the corresponding diff card into view; expand if collapsed.
- Per-file collapse toggle: clicking the "Show diff" / "Hide diff" button on a `data-large="true"` card toggles a CSS class — purely client-side, no fetch. The diff content is already in the DOM after the initial `Diff2HtmlUI.draw` call.
- Dark-mode sync: read `document.documentElement.classList.contains('dark')` and pass `colorScheme: 'dark' | 'light'` to `Diff2HtmlUI`. Listen for the existing theme-toggle event (or observe class changes via `MutationObserver` on `documentElement`) and re-render when it changes.
- Generated-file glob list: keep a single canonical list in JS that matches `orch.diff_service.GENERATED_FILE_GLOBS` exactly (Invariant 8). Either embed it inline or fetch it from a small backend endpoint; inline is simpler for v1. Do NOT diverge.

Keyboard shortcuts (nice-to-have): `j`/`k` next/prev file in tree, `t` focus filter, `o` toggle expand. Implement them only if simple — do not block the step on keyboard niceties.

### 5. `dashboard/templates/pages/project/item_detail.html`

Replace the Artifacts tab button (~line 58) with:

```html
<button hx-get="/project/{{ current_project.id }}/item/{{ item.id }}/tab/files"
        hx-target="#tab-content"
        ...same classes/attributes as existing tab buttons...>
  Files
</button>
```

Keep all other tab buttons untouched.

### 6. `dashboard/static/styles.css`

Append plain CSS rules ONLY if `make css` is unable to compile Tailwind (per `CLAUDE.md` rule). Likely additions:

- Status badge variants (`.diff-status-A`, `.diff-status-M`, `.diff-status-D`, `.diff-status-R`) with both background color and bold-letter typography.
- `+N −M` proportional bar styles (`.diff-bar`, `.diff-bar .add`, `.diff-bar .del`).
- Sticky filename header (`.diff-card-header { position: sticky; top: 0; z-index: 10; }`).

Run `make css` first; if it succeeds with the Tailwind classes in your templates, no CSS append is needed.

### 7. Delete `dashboard/templates/fragments/item_artifacts.html`

After confirming no other route references it (S05 already pruned the route).

## Project Conventions

Read `dashboard/CLAUDE.md`:
- Fragment templates MUST NOT extend `base.html`.
- htmx is the AJAX layer; avoid React/Vue/SPA patterns.
- Tailwind classes preferred; plain CSS append only when Tailwind CLI fails.
- `window.iwClipboard.copy(...)` helper for any clipboard buttons (not strictly needed here unless you add a "Copy diff to clipboard" action).
- `playwright-cli` is the ONLY browser automation tool — but that's S09/S19, not this step.

## Accessibility (WCAG 1.4.1 — Use of Color)

- Status conveyed by both color AND letter on badges.
- Unified-diff `+`/`−` line prefixes never stripped.
- Sufficient contrast on diff backgrounds in both light and dark modes (`bg-green-50 dark:bg-green-950/30` for adds; `bg-red-50 dark:bg-red-950/30` for deletes — these desaturated backgrounds work for deuteranopia).

## TDD Requirement

Frontend templates are exercised via FastAPI TestClient (HTML structure assertions) in S09 and via `playwright-cli` in S19. For your step:
- Confirm `make css` runs cleanly (or document that you appended plain CSS instead).
- Manually open the dashboard once and visit the Files tab on at least one item to smoke-test rendering. Capture a post-state screenshot if a dev environment is available.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint` (includes `node --check` on `dashboard/static/**/*.js` per `Makefile:26`)

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-frontend`

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "frontend-impl",
  "work_item": "F-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/item_files.html",
    "dashboard/templates/fragments/item_files_untracked.html",
    "dashboard/templates/components/libs/diff2html.html",
    "dashboard/static/vendor/diff2html/<version>/diff2html.min.css",
    "dashboard/static/vendor/diff2html/<version>/diff2html-ui-slim.min.js",
    "dashboard/static/vendor/diff2html/<version>/LICENSE",
    "dashboard/templates/pages/project/item_detail.html",
    "dashboard/static/files.js",
    "dashboard/static/styles.css"
  ],
  "files_deleted": [
    "dashboard/templates/fragments/item_artifacts.html"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
