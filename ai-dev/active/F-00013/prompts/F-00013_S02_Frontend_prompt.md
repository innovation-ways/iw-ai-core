# F-00013_S02_Frontend_prompt

**Work Item**: F-00013 — Project-Level Documentation System — Automation (Phase 3)
**Step**: S02
**Agent**: Frontend

---

## Input Files

- `ai-dev/active/F-00013/F-00013_Feature_Design.md` — Design document
- `ai-dev/work/F-00013/reports/F-00013_S01_Backend_report.md` — S01 report
- `dashboard/templates/fragments/docs_card.html` — Existing doc card
- `dashboard/templates/docs_library.html` — Existing library page
- `dashboard/templates/docs_detail.html` — Existing detail page
- `dashboard/routers/docs.py` — Extend with new routes
- `dashboard/CLAUDE.md`

## Output Files

- `dashboard/templates/fragments/docs_card.html` — Modified: staleness badge
- `dashboard/templates/docs_library.html` — Modified: staleness summary row + settings icon
- `dashboard/templates/fragments/docs_stale_summary.html` — New
- `dashboard/templates/fragments/docs_config_panel.html` — New
- `dashboard/templates/fragments/docs_lint_warnings.html` — New
- `dashboard/routers/docs.py` — Extended with config routes + stale summary route
- `ai-dev/work/F-00013/reports/F-00013_S02_Frontend_report.md` — Step report

## Context

You are implementing the automation UI for **F-00013: Documentation Automation**. This step adds staleness indicators, a "Regenerate All" control, an editorial lint warnings callout, and a project-level doc config panel. All components must integrate with the existing Phase 1/2 UI without visual regressions.

## Requirements

### 1. Staleness Badge on Doc Cards

Modify `docs_card.html` to show a staleness indicator when `doc.is_stale == True` (computed in the route context by calling `DocService.get_stale_docs()` and cross-referencing):

```
[⚠ Stale] badge
```

- Color: `bg-yellow-100 text-yellow-800 border border-yellow-300`
- Icon: warning triangle (use existing icon library)
- Tooltip (`title` attribute): "Source changed: docs/auth/middleware.py (3h ago)"
- Position: top-right corner of the card, overlapping the type badge row

The `docs_library.html` route context must pass a `stale_doc_ids: set[str]` to the template so cards can check `doc.id in stale_doc_ids`.

### 2. Staleness Summary Row (`docs_stale_summary.html`)

A dismissible banner shown above the card grid when any docs are stale:

```
⚠  3 documents are stale — their source files have changed since last generation.
   [Regenerate All Stale]   [Dismiss]
```

- Background: `bg-yellow-50 border border-yellow-200`
- "Regenerate All Stale" button: `hx-post="/api/project/{id}/docs/regenerate-stale"`, `hx-target="#stale-summary"`, `hx-swap="outerHTML"` (replace with success message)
- "Dismiss": sets a session cookie / localStorage key to hide for 24h (client-side JS)
- After POST: replace banner with "Queued N jobs for regeneration" success message (green, auto-dismiss after 5s)

Add to `docs_library.html`: `<div id="stale-summary" hx-get="/api/project/{id}/docs/stale" hx-trigger="load" hx-swap="innerHTML"></div>` just above the filter bar.

### 3. Lint Warnings Callout (`docs_lint_warnings.html`)

On the document detail page, shown when `doc`'s most recent completed `DocGenerationJob` has non-empty `lint_warnings`:

```
┌──────────────────────────────────────────────────────┐
│ ⚠  Editorial Lint Warnings (last generation)         │
│                                                      │
│ • [required_section_purpose] Missing "## Purpose"    │
│   section — required for technical documents.        │
│ • [forbidden_phrase] Found "cutting-edge" — avoid    │
│   marketing language in technical docs.              │
└──────────────────────────────────────────────────────┘
```

- Color: `bg-amber-50 border border-amber-300`
- Each warning: rule name in monospace, message in normal text
- Shown in the left content column, just above the rendered markdown
- htmx-loaded: `hx-get="/api/project/{id}/docs/{doc_id}/lint-warnings"`, `hx-trigger="load"`

Add the lint warnings route to `docs.py`: returns this fragment with `job.lint_warnings` from the most recent completed job.

### 4. Doc Configuration Panel (`docs_config_panel.html`)

A settings panel accessible via a gear icon (⚙) in the Docs library page header.

When clicked: `hx-get="/api/project/{id}/docs/config"` opens an overlay/drawer with:

```
Documentation Settings

Auto-trigger generation on batch merge
[Toggle ON/OFF]

Staleness threshold
[24] hours

Forbidden phrases  
[cutting-edge, state-of-the-art, ...]  (editable tag list)

[Save Settings]  [Cancel]
```

- Toggle: Tailwind-styled checkbox toggle (same pattern as existing dashboard toggles)
- Threshold: number input, min=1, max=720
- Forbidden phrases: comma-separated text input (space-separated tags displayed as chips)
- Save button: `hx-post="/api/project/{id}/docs/config"`, `hx-encoding="application/json"` (or form), replaces panel with "Settings saved ✓"

**Routes to add in `docs.py`:**
```
GET  /api/project/{id}/docs/config   → render docs_config_panel.html with current config
POST /api/project/{id}/docs/config   → save to Project.config["doc_generation"], return success fragment
GET  /api/project/{id}/docs/stale    → call DocService.get_stale_docs(), render docs_stale_summary.html
POST /api/project/{id}/docs/regenerate-stale → create jobs for all stale docs, return count fragment
```

### 5. Settings Gear Icon in Library Header

Modify `docs_library.html` page header to add a settings gear icon:
- Small, subtle (text-gray-400 hover:text-gray-600)
- Positioned top-right of the page header area
- `hx-get="/api/project/{id}/docs/config"`, `hx-target="#docs-config-overlay"`, `hx-swap="innerHTML"`
- Add `<div id="docs-config-overlay"></div>` as a fixed overlay container

## Project Conventions

- Read `dashboard/CLAUDE.md` before modifying any template
- All new interactive elements need accessible labels
- Config panel must be keyboard-accessible (focus trap when open)
- htmx patterns must match existing dashboard patterns exactly

## Test Verification (NON-NEGOTIABLE)

1. `make quality` — ruff + mypy pass
2. Describe in report: manually verified staleness badge appears on stale cards, config panel opens/saves, lint warnings appear on detail page

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "Frontend",
  "work_item": "F-00013",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/docs_card.html",
    "dashboard/templates/docs_library.html",
    "dashboard/templates/fragments/docs_stale_summary.html",
    "dashboard/templates/fragments/docs_config_panel.html",
    "dashboard/templates/fragments/docs_lint_warnings.html",
    "dashboard/routers/docs.py"
  ],
  "tests_passed": true,
  "test_summary": "quality checks passed",
  "blockers": [],
  "notes": ""
}
```
