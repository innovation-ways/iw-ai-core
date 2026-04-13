# F-00014_S03_Frontend_prompt

**Work Item**: F-00014 — Project-Level Documentation System — Polish (Phase 4)
**Step**: S03
**Agent**: Frontend

---

## Input Files

- `ai-dev/active/F-00014/F-00014_Feature_Design.md` — Design document (UI sections; use this for all route URLs — S02 runs in parallel)
- `ai-dev/work/F-00014/reports/F-00014_S01_Backend_report.md` — S01 report
- `dashboard/templates/fragments/docs_version_drawer.html` — Existing version drawer (from F-00011)
- `dashboard/templates/docs_detail.html` — Existing detail page
- `dashboard/templates/docs_library.html` — Existing library page
- `dashboard/CLAUDE.md`

## Output Files

- `dashboard/templates/fragments/docs_version_drawer.html` — Modified: add version select + compare button
- `dashboard/templates/fragments/docs_diff.html` — New: diff viewer fragment
- `dashboard/templates/docs_global.html` — New: global docs search page
- `dashboard/templates/fragments/docs_global_results.html` — New: htmx search results
- `dashboard/templates/fragments/docs_broken_links.html` — New: broken links callout
- `dashboard/templates/docs_library.html` — Modified: add multi-select + export button
- `dashboard/templates/fragments/docs_card.html` — Modified: add per-card checkbox and export button
- `dashboard/templates/fragments/nav_main.html` — Modified: add "Docs" top-level nav entry (if exists)
- `ai-dev/work/F-00014/reports/F-00014_S03_Frontend_report.md` — Step report

## Context

You are implementing the polish UI for **F-00014: Documentation Polish**. This is the most frontend-heavy step of the entire feature — version diffs, a global search page, multi-select export, and broken link warnings. The goal is a polished, production-quality UI. Read `dashboard/CLAUDE.md` first and study existing templates carefully.

## Requirements

### 1. Version Diff Viewer (`docs_diff.html`)

Displayed inline in the Version History drawer after the user selects two versions and clicks "Compare".

**Version selection in `docs_version_drawer.html`:**
- Add a checkbox to each version row (`id="v-select-{version}"`)
- "Compare" button appears (via `x-show` or class toggle) when exactly 2 checkboxes are checked
- JavaScript: listen for checkbox changes, enable Compare button when count == 2, disable otherwise
- Compare button: `hx-get="/api/project/{id}/docs/{doc_id}/diff?v1={older}&v2={newer}"`, `hx-target="#diff-viewer"`, `hx-swap="innerHTML"`
- `<div id="diff-viewer"></div>` inserted just below the version list in the drawer

**Diff viewer HTML structure:**
```html
<div class="diff-viewer font-mono text-sm">
  <div class="diff-header flex justify-between text-gray-500 text-xs px-2 py-1 bg-gray-50 border-b">
    <span>v{old}</span>
    <span>v{new}</span>
  </div>
  <!-- For each diff line: -->
  <div class="diff-line-added bg-green-50 text-green-800 px-2 py-0.5">+ {line}</div>
  <div class="diff-line-removed bg-red-50 text-red-800 px-2 py-0.5">- {line}</div>
  <div class="diff-line-context text-gray-600 px-2 py-0.5">  {line}</div>
  <div class="diff-line-hunk text-blue-600 bg-blue-50 px-2 py-0.5 text-xs">@@ ... @@</div>
</div>
```

- "No differences found" state: centered gray text "These versions are identical."
- Diff capped at 100 lines display; if more: "Showing first 100 lines of diff — {total} total lines" with "Show all" button
- Close diff button: `hx-on:click="document.getElementById('diff-viewer').innerHTML = ''"` + reset checkboxes

**Desktop vs mobile:**
- Desktop: show `+` and `-` lines side by side would require JS table magic — instead, use unified view on all breakpoints (simpler, correct)

### 2. Global Docs Search Page (`docs_global.html`)

Full page at `/docs` — not a project-scoped page.

**Layout:**
- Full-width centered content, max-w-4xl
- Platform branding header: "Documentation" as H1, "Search across all project documentation" subtitle
- Large search bar: `<input hx-get="/api/docs/search" hx-trigger="input changed delay:300ms" hx-target="#global-results" placeholder="Search documentation..." class="w-full text-lg px-4 py-3 ...">`
- Filter row (below search bar): doc_type pills, status pills, tier pills, project dropdown (select element with all project names)
- Each filter change: triggers same htmx search with combined params

**Results container `id="global-results"`:**
- Initial state (no search yet): "Enter a search term to find documentation across all projects"
- Loading state: htmx `hx-indicator` spinner

**Results fragment `docs_global_results.html`:**
- Results grouped by project (project name as `<h3>` section header with a subtle divider)
- Each result card (more compact than the library card):
  ```
  [Type Badge]  Title                         [Project chip]
  Status · Tier · v{version}
  "...matched excerpt with highlighted terms..."
  ```
- Highlighted terms: wrap `<mark class="bg-yellow-200 rounded px-0.5">` around matches (the `ts_headline()` output uses `<b>` tags — convert `<b>` to `<mark>` in the template filter)
- "X results across Y projects" count line above results
- Empty state: "No documentation found for '{query}'" with suggestions

### 3. Multi-Select Export UI on Library Page

Modify `docs_library.html`:

**Select mode toggle button** in the page header area:
- "Select" button (outline style); clicking enters select mode
- In select mode: checkboxes appear on each card (top-left corner); button changes to "Cancel"

**Per-card checkbox** (modify `docs_card.html`):
- Hidden by default; shown when select mode active (via `data-select-mode` on parent div, CSS sibling selector)
- `<input type="checkbox" class="doc-select-checkbox" value="{doc.doc_id}">`

**Floating action bar** (fixed bottom, appears when ≥1 selected):
- `<div id="export-action-bar" class="fixed bottom-6 left-1/2 -translate-x-1/2 ...">`
- Content: "{N} selected · [Export Selected] [Clear]"
- "Export Selected": builds `doc_ids` from checked checkboxes via JavaScript → navigates to `GET /api/project/{id}/docs/export?doc_ids={joined}` (opens as download)
- "Clear": unchecks all, hides action bar
- JavaScript: `document.querySelectorAll('.doc-select-checkbox:checked')` to collect values

**Per-card export button** (in card actions menu):
- Existing "View" button becomes a dropdown (or add a second button):
  ```
  [View]  [↓ Export]
  ```
- Export: `<a href="/api/project/{id}/docs/{doc_id}/export" download>` — direct link

### 4. Broken Links Callout (`docs_broken_links.html`)

On the document detail page, loaded via htmx:

```html
<!-- If broken_links is non-empty: -->
<div class="bg-orange-50 border border-orange-300 rounded-lg p-4 mb-4">
  <div class="flex items-center gap-2 mb-2">
    <span class="text-orange-600">⚠</span>
    <h4 class="font-semibold text-orange-800">N Broken Links</h4>
    <button hx-get="/api/project/{id}/docs/{doc_id}/validate-links" 
            hx-target="#broken-links-callout" class="ml-auto text-sm text-orange-600 underline">
      Re-check
    </button>
  </div>
  <ul class="text-sm space-y-1">
    <li class="flex gap-2">
      <span class="text-orange-500">internal</span>
      <code class="text-orange-700">docs/auth/missing.md</code>
      <span class="text-orange-500">not_found</span>
    </li>
  </ul>
</div>
<!-- If no broken links: green "All links valid ✓" -->
```

Add `<div id="broken-links-callout" hx-get="/api/project/{id}/docs/{doc_id}/validate-links" hx-trigger="load">` at the top of the detail page content column (if `doc.broken_links` is not None).

### 5. Top-Level Nav "Docs" Entry

Find the main platform navigation template (the one with project selector, settings, etc. — check `dashboard/templates/base.html` or equivalent).

Add a "Docs" entry:
- Icon: book or document icon
- Label: "Docs"
- href: `/docs`
- Active state when `request.url.path.startswith("/docs")`

If no top-level nav exists (only project-level sidebar), add it to the global header bar.

## Project Conventions

- Read `dashboard/CLAUDE.md` before any template changes
- JavaScript must be vanilla (no new JS frameworks) or Alpine.js if already used
- All new interactive elements must have proper `aria-*` attributes
- Diff viewer must be keyboard-navigable (Tab between versions, Enter to compare)
- Multi-select mode must not break the existing filter/search functionality

## Test Verification (NON-NEGOTIABLE)

1. `make quality` — ruff + mypy pass
2. Describe in report: manually verified diff viewer, global search, multi-select export, broken links callout

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Frontend",
  "work_item": "F-00014",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/docs_version_drawer.html",
    "dashboard/templates/fragments/docs_diff.html",
    "dashboard/templates/docs_global.html",
    "dashboard/templates/fragments/docs_global_results.html",
    "dashboard/templates/fragments/docs_broken_links.html",
    "dashboard/templates/docs_library.html",
    "dashboard/templates/fragments/docs_card.html",
    "dashboard/templates/fragments/nav_main.html"
  ],
  "tests_passed": true,
  "test_summary": "quality checks passed",
  "blockers": [],
  "notes": ""
}
```
