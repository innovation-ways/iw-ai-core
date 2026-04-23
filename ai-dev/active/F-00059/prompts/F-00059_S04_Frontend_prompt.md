# F-00059_S04_Frontend_prompt

**Work Item**: F-00059 — Functional design documents for work items
**Step**: S04
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network mutation command.
See S01 banner for the full list.

---

## Input Files

- `ai-dev/active/F-00059/F-00059_Feature_Design.md` — see *Frontend Changes* and *AC3*
- `dashboard/routers/items.py` — existing `item_detail` route (~line 762) and the existing `item_tab_design_doc` route (~line 847)
- `dashboard/templates/fragments/item_design_doc.html` — existing design-doc tab fragment (copy as a structural reference)
- `dashboard/templates/pages/project/item_detail.html` — existing tab layout (~lines 23–84)
- `dashboard/CLAUDE.md` — htmx conventions

## Output Files

- `ai-dev/active/F-00059/reports/F-00059_S04_Frontend_report.md` (new)
- `dashboard/routers/items.py` (modified — new route)
- `dashboard/templates/fragments/item_functional_doc.html` (new)
- `dashboard/templates/pages/project/item_detail.html` (modified — one new tab button)

## Context

S01 / S02 populate `work_items.functional_doc_content`. This step surfaces
that content in the dashboard's item detail page as a new tab, immediately
after the existing "Design Document" tab. No other UI areas are touched.

## Requirements

### 1. New route — `dashboard/routers/items.py`

Mirror the existing `item_tab_design_doc` function (around line 847). Create a
sibling function (suggested name `item_tab_functional_doc`) handling:

```
GET /project/{project_id}/item/{item_id}/tab/functional-doc
```

Behaviour:

- Look up the WorkItem by `(project_id, item_id)`; 404 if missing — match the
  existing tab routes' error handling exactly.
- If `item.functional_doc_content` is non-NULL and non-empty, render via the
  project's existing markdown helper (same helper the design-doc tab uses) and
  pass the HTML to the new fragment.
- If `functional_doc_content` is NULL/empty AND `functional_doc_path` points to
  an existing on-disk file, fall back to reading that file (mirroring the
  design-doc tab's fallback). If neither is available, render the fragment
  with an empty content string and let the template show its empty state.
- Return the fragment `item_functional_doc.html` — NOT the full page.
- Keep the function under the same authorization guard the other tab routes
  use (if any).

Register the route in the same router; do not create a new router file.

### 2. New fragment — `dashboard/templates/fragments/item_functional_doc.html`

Start from `item_design_doc.html`'s structure (same outer wrapper, same
markdown container styling). Diverge where needed:

- Title: "Functional Design" (no "Document" suffix — the technical tab is
  labelled "Design Document" and the visual contrast helps).
- When the rendered markdown is empty, render a friendly empty state: a light
  box containing: *"No functional design document has been loaded for this
  item yet. If the item is new, the design phase will generate one. For
  existing items, run `scripts/backfill_functional_doc.py <ID> --load-db` to
  populate it."*
- No inline JavaScript. All interactivity via htmx, matching the existing
  fragment.

### 3. Tab button — `dashboard/templates/pages/project/item_detail.html`

The existing tab row (see the `Design Document` button around line 32) uses
htmx `hx-get` + `hx-target` attributes. Duplicate that button immediately
after it. Button label: *Functional Design*. `hx-get` pointing at the new
route created in §1. `hx-target` to the same content container as the other
tabs. Use the same class names as the neighbour button for visual parity.

The default landing tab must remain *Design Document* — do NOT change the
initial `hx-trigger="load"` (or equivalent) that preselects the current tab.

### 4. No changes to sibling tabs

Open every existing tab (Overview, Design Document, Reports, Artifacts,
Evidences, Logs, Fix Cycles, Execution Report) in the local dashboard after
your changes and verify:

- Each still renders correctly.
- The order is unchanged (new tab is inserted between Design Document and
  Reports — second position in the tab row).
- No console errors.

Screenshots from this local verification are evidence for the step report
(not the final browser step, which runs in S12 on the isolated E2E stack).

## Project Conventions

Read `dashboard/CLAUDE.md`. htmx only — no React, no Alpine. Jinja2
templates. Fragments under `dashboard/templates/fragments/`. Follow the
existing naming pattern `item_*.html`.

## TDD Requirement

Integration tests for the route live in S05's
`tests/integration/test_dashboard_item_functional_tab.py`. For this step,
add a Jinja reproduction check in the report: a minimal `jinja2.Environment`
rendering of the new fragment with (a) content populated and (b) content
empty, captured as two HTML snippets in the step report so the reviewer can
see the output shape without booting the full dashboard.

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — pass.
2. `make lint` — pass.
3. `make test-frontend` — pass (if applicable; this repo's frontend tests
   may be thin).

## Subagent Result Contract

Standard JSON with `step: "S04"`, `agent: "frontend-impl"`, `work_item: "F-00059"`.
