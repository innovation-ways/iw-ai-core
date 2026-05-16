# F-00085_S10_Frontend_prompt

**Work Item**: F-00085
**Step**: S10
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Input Files

- `ai-dev/active/F-00085/F-00085_Feature_Design.md` — AC1..AC14, file manifest
- S08 deliverables (already merged): the 7 endpoints and their template paths
- Existing patterns:
  - `dashboard/templates/base.html` — header layout, sidebar nav, htmx imports
  - `dashboard/templates/pages/project/jobs.html` — closest precedent for "list page with rollup widgets"
  - `dashboard/templates/fragments/jobs_table.html` — fragment with htmx swap targets
  - `dashboard/static/styles.css` — current style additions; CR-00033 fallback rule applies
- `dashboard/CLAUDE.md` for layer conventions
- Project memory `feedback_skills_sync` and CR-00033 are relevant

## Output Files

- `ai-dev/active/F-00085/reports/F-00085_S10_Frontend_report.md`

## Context

Build the Auto-Merge dashboard surface. One page + 6 fragments + chip include in `base.html` + sidebar nav row + CSS append.

## Requirements

### 1. Page template `dashboard/templates/pages/project/auto_merge.html`

- Extends `base.html` (standard pattern).
- Block structure: title, content.
- Content layout:
  - At top: a "page header" strip with the project name + the rich status chip (NOT the compact one used in base.html — this one shows more detail).
  - **If `status.config.phase == 0`** (AC6): show the empty-state panel ("Resolver is in plumbing-only mode for this project. Use Settings to enable Phase 1 dry-run.") + the Settings panel (operator still needs the control to enable it). Hide the events table, refuse-list widget, and rollups.
  - **If `status.config.phase >= 1`**: render the full page with these sections (top-to-bottom):
    1. Status chip (rich) — phase, runtime, deployed_since timestamp, total events count, health indicator
    2. Settings panel — phase dropdown, runtime picker, "Use global default" radio, Save button
    3. Verdict + cost rollup (htmx loads `/<project>/auto-merge/rollup?window=7d`)
    4. Refuse-list activity widget (hidden when all zero per AC7)
    5. Events table (htmx pagination, type filter)
- Use `hx-get`, `hx-target`, `hx-swap` for all dynamic regions per existing patterns.

### 2. Fragment `dashboard/templates/fragments/auto_merge_status_chip.html`

- Two variants:
  - **Header (compact)**: small pill, single line. Used in `base.html`. Includes phase, cli_tool/model, attempts-count, health icon. Hidden when `status.config.phase == 0` (Invariant 6 — Jinja conditional, NOT CSS display:none).
  - **Page (rich)**: larger card on the page itself, more detail (deployed_since timestamp, runtime source, current overrides if any).
- Single template; use a `{% if compact %}` flag passed by the includer.
- Health-state colour: `healthy` → green, `degraded` → yellow, `down` → red, `unknown` → grey.
- "Per-project override" annotation when `status.config.source == "per_project_db"`.

### 3. Fragment `dashboard/templates/fragments/auto_merge_events_table.html`

- Table with columns: timestamp, event_type, entity_id, message (truncated), verdict widget, actions.
- Rows for `merge_auto_resolved` show an INLINE verdict widget (4 buttons: pending/correct/wrong/partial). Active verdict is highlighted.
- Inline verdict button `hx-post`'s to `/<project>/auto-merge/events/<event_id>/verdict` with body `{verdict: "<value>"}`; swap target is the row itself (`hx-swap="outerHTML"`).
- Other event types (no verdict widget) show a `(view)` link that opens the detail modal (`hx-get` → `/<project>/auto-merge/events/<id>` → swap into modal container).
- Pagination footer: "Showing N-M of TOTAL" + Prev/Next htmx links.
- Type filter chips at top: `[all] [resolved] [attempted] [failed] [skipped] [health_probe] [config_updated]`.

### 4. Fragment `dashboard/templates/fragments/auto_merge_event_detail.html`

- Modal scaffold (matches existing modal patterns in `dashboard/templates/fragments/*modal*.html`).
- Top: event metadata (timestamp, type, entity_id, project_id).
- Middle: for `merge_auto_resolved` events with `diffs` populated, render side-by-side diff per file. The `difflib.HtmlDiff` output already contains the table HTML — render it inside a `<div class="diff-viewer">…</div>` wrapper.
  - If `current_text` was None / fetch failed → show "(file no longer exists on main)" placeholder.
  - If multiple files: use a small tabs widget (CSS-only, no JS needed).
- Bottom: verdict widget (same 4 buttons as inline) + notes textarea + Save button. Save POSTs to the verdict endpoint with `notes` body field.
- Modal can be dismissed via close button OR clicking the backdrop.

### 5. Fragment `dashboard/templates/fragments/auto_merge_rollup.html`

- Three widgets side-by-side:
  - **Verdict rollup**: shows counts for pending/correct/wrong/partial, with a calculated accuracy ratio (correct / (correct+wrong+partial), pending excluded). Window selector: 7d / 30d tabs.
  - **Token cost rollup**: total input/output tokens + $ cost; per-model breakdown table (model, input tok, output tok, $). Banner if `has_unknown_models`.
  - **Refuse-list breakdown**: counts grouped by reason (refuse_list / mixed_refuse_list / phase_0 / binary / not_allowlisted / hunk_too_large / too_many_files / runtime_option_missing). Render as a small horizontal bar with counts.

### 6. Fragment `dashboard/templates/fragments/auto_merge_refuse_list.html`

- May be the same as the refuse-list portion of `auto_merge_rollup.html`, OR a standalone widget. Pick the cleanest factoring — if duplication is < 20 lines, consolidate into rollup.html.
- AC7: hidden entirely when total count is 0.

### 7. Fragment `dashboard/templates/fragments/auto_merge_settings.html`

- Form fields:
  - **Phase**: a `<select>` with options `0` and `1` (NEVER `2` or `3` — Inv 5). Plus a "Use global default" radio.
  - **Runtime**: a `<select>` with `<optgroup>` per `cli_tool` (claude vs opencode), each containing `<option value="<id>">{model_label}</option>` for enabled rows. Plus a "Use global default" radio for runtime.
  - **Save** button: htmx `hx-post` to `/<project>/auto-merge/config` with the form values; `hx-target` = the status chip card; `hx-swap="outerHTML"`.
- When "Use global default" radio is selected for phase, send `phase=null` in body. Same for runtime.
- Below the form: a small "Last changed" annotation showing `updated_at` + `updated_by` for the existing row (or "Using global default" when no row).

### 8. `base.html` edits

- One `{% include 'fragments/auto_merge_status_chip.html' with compact=True %}` inside the header (next to existing project nav badges).
- The include must be wrapped in `{% if current_project and request.state.auto_merge_phase_for_chip >= 1 %}` — the chip is hidden when phase=0 (Invariant 6).
- One sidebar nav tuple addition: `('/auto-merge', 'Auto-Merge')`.

> **Implementation hint**: To get the resolved phase into `request.state` without a query per page render, add a middleware OR cache the resolved config on the `current_project` dependency. The cheapest path: in the `current_project` dependency (probably `dashboard/dependencies.py`), call `auto_merge_aggregator.resolve_project_config(db, project_id, toml_config)` and attach the result to `request.state.auto_merge_status`. If that file is out of scope for this Feature, instead add the chip include block to a fragment that runs its own htmx-fetch on page load — but inline is much faster.

### 9. CSS additions in `dashboard/static/styles.css`

- Use the CR-00033 fallback rule: APPEND plain CSS rules directly to the file. Tailwind may or may not be available; do not rely on `make css`.
- Add styles for: status chip (compact + rich variants), settings panel, diff viewer wrapper, verdict button states (pending/correct/wrong/partial), refuse-list widget, modal backdrop.
- Target line count: ~50 lines max.
- Use existing colour palette (greens, yellows, reds, greys).

### 10. Jinja `format` filter gotcha

Per CLAUDE.md Critical Rules: use `%`-style format strings inside Jinja `format` filter (e.g., `"%d events"|format(n)`), NEVER `{}`-style. The pre-commit lint enforces this (`scripts/check_templates.py`).

### 11. NO new JS code

- Use htmx attributes only. Tab switching can be CSS `:target` + radio inputs. Modal can be htmx hx-get + hx-target into a body container.
- If you reach for `<script>`, stop and rethink — there's almost always an htmx pattern.

## Project Conventions

- Read `dashboard/CLAUDE.md`.
- Templates use Jinja2; reference DI vars: `request`, `current_project`, `status`, etc.
- Existing templates use Tailwind-style class names in HTML; new CSS rules in styles.css use plain selectors (CR-00033 fallback).

## TDD Requirement

Templates are evidence-by-rendering, not by assertion. **RED**: write a dashboard TestClient test in `tests/dashboard/test_auto_merge_routes.py` (it should already exist from S08) that asserts a specific text string appears in the page response (e.g., "Auto-Merge Resolver" header) — but this test will be expanded in S13.

`tdd_red_evidence` can be `"n/a — frontend template; behavioural coverage via dashboard TestClient in S13 + browser verification in S24"`.

## Pre-flight Quality Gates

1. `make format`.
2. `make typecheck` — should be no-op (no Python changes).
3. `make lint` — INCLUDING `scripts/check_templates.py` for the `%`-format-filter rule.
4. Targeted: `uv run pytest tests/dashboard/test_auto_merge_routes.py -v` (already wired by S08).

## Test Verification

- Run only the dashboard tests for the auto-merge routes.

## Subagent Result Contract

```json
{
  "step": "S10",
  "agent": "frontend-impl",
  "work_item": "F-00085",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/templates/pages/project/auto_merge.html",
    "dashboard/templates/fragments/auto_merge_status_chip.html",
    "dashboard/templates/fragments/auto_merge_events_table.html",
    "dashboard/templates/fragments/auto_merge_event_detail.html",
    "dashboard/templates/fragments/auto_merge_rollup.html",
    "dashboard/templates/fragments/auto_merge_refuse_list.html",
    "dashboard/templates/fragments/auto_merge_settings.html",
    "dashboard/templates/base.html",
    "dashboard/static/styles.css"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed (route renderability tests; full AC matrix in S13/S24)",
  "tdd_red_evidence": "n/a — frontend templates; behavioural coverage via dashboard TestClient in S13 + browser verification in S24",
  "blockers": [],
  "notes": "Chip include in base.html gated on phase>=1 (Inv 6). All fragments use htmx; no new JS. CSS appended per CR-00033. Settings phase dropdown offers ONLY 0/1 (Inv 5). Disabled runtimes excluded from picker (defence-in-depth with S08 API re-validation)."
}
```
