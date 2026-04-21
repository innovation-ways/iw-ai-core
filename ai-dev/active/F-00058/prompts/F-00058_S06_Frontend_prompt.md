# F-00058_S06_Frontend_prompt

**Work Item**: F-00058
**Step**: S06
**Agent**: frontend-impl

---

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md` — Frontend Changes + AC1–AC7
- `ai-dev/active/F-00058/evidences/pre/F-00058-project-page-before.png` — pre-state
- `dashboard/templates/pages/project/` — existing project pages to match style
- `dashboard/templates/fragments/` — existing fragments to pattern-match
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S06_Frontend_report.md`
- `dashboard/templates/pages/project/oss.html` (new)
- `dashboard/templates/fragments/oss_status_pill.html` (new)
- `dashboard/templates/fragments/oss_status_frame.html` (new)
- `dashboard/templates/fragments/oss_domain_card.html` (new)
- `dashboard/templates/fragments/oss_tool_run_card.html` (new)
- `dashboard/templates/fragments/oss_install_modal.html` (new)
- `dashboard/templates/fragments/oss_cli_block.html` (new)
- `dashboard/templates/fragments/oss_scan_progress.html` (new)
- Project-page header template (modified — add OSS Status frame slot under Git Status)
- Project-tabs partial (modified — conditional "OSS" tab)
- `dashboard/static/css/*.css` (modified if needed — no new JS framework)

## Context

Build the OSS view and pill. Read `dashboard/CLAUDE.md` first for htmx/tailwind/hyperscript conventions. Read the existing Git Status frame (likely in `dashboard/templates/pages/project/_header.html` or similar) to understand how frames are styled — the OSS Status frame must match its visual weight.

Every template must use the same htmx/CSS idioms as existing fragments — do not introduce a new framework.

## Requirements

### 1. Status pill fragment — 4 states

`oss_status_pill.html`:
- Renders one pill: 🟢 green / 🟡 yellow / 🔴 red / ⚫ gray.
- Input context: `pill_color`, `summary_text`, `stale` (bool), `url`.
- Clickable — navigates to the OSS view.
- If `stale=True`, annotate with ⚠ icon + "stale" tooltip.

### 2. Status frame (underneath Git Status on every project page)

`oss_status_frame.html`:
- Frame with a heading "OSS Status".
- When `oss_enabled=false`: shows an "Install OSS" button that opens the install modal.
- When `oss_enabled=true`: renders the pill + a short summary + "Rescan" shortcut.
- Must match the Git Status frame's visual treatment.
- Included in the shared project-page header so every project view (Code, Tests, Quality, Documentation, OSS) shows it.

### 3. OSS page — main view

`pages/project/oss.html`:
- Action row: Scan / Prepare / Publish buttons.
- Each button has an adjacent collapsible "Run it yourself" block (`oss_cli_block.html`) showing the equivalent `uv run iw oss …` command.
- Below: stale banner (if stale), progress row (if scan running), results tree.
- Results tree = collapsible domain cards (`oss_domain_card.html`), each containing findings + per-tool cards (`oss_tool_run_card.html`).
- Toast region for errors / confirmations.

### 4. Install modal

`oss_install_modal.html`:
- Fetched from `GET /projects/{id}/oss/tools`.
- Lists every Tier-1 tool with ✅ installed / ❌ missing.
- For each missing tool, a copy-button for the install command.
- "Install now" button POSTs to a new endpoint (we'll add in F-00058 or defer to a follow-up — coordinate with S05; if deferred, show the commands and let the user run manually).
- "Enable OSS" button only enabled when all required tools present; POSTs to `/enable`.

### 5. Scan progress row

`oss_scan_progress.html`:
- Subscribes to `GET /projects/{id}/oss/stream/{job_id}` via `hx-sse`.
- Shows last N (≈5) stdout lines scrolling.
- On `complete` event, swaps itself with the refreshed results tree.
- On `error`, shows error toast with retry button.

### 6. CLI block fragment

`oss_cli_block.html`:
- Collapsible `<details>` with a `<summary>` "Run it yourself" and a `<code>` block.
- Context inputs: `command` (string), `description` (string).
- Copy-to-clipboard button.

### 7. Domain + tool-run cards

- `oss_domain_card.html`: domain header, finding count by severity, collapsible body with finding rows.
- `oss_tool_run_card.html`: tool name, version badge, runtime, verdict badge, expandable details panel with first 2KB of output.

### 8. Tab visibility

Project tab row partial — add an "OSS" tab between existing tabs (order to be decided — likely after Quality), conditional on `project.oss_enabled`.

## Project Conventions

- Per `dashboard/CLAUDE.md`: match existing fragment naming, htmx header patterns, tailwind utility usage.
- NEVER hardcode colors; use tailwind utility classes matching the existing pill / badge patterns.
- No new JS framework — htmx + hyperscript (if used elsewhere) only.
- Accessibility: `aria-label` on pill, keyboard-accessible collapsibles, focus management on modal open/close.

## TDD Requirement

Jinja reproduction tests (per I-00033 pattern in `tests/integration/`):
- `tests/integration/test_oss_dashboard_templates.py`:
  - Pill renders correct color class for each of 4 states.
  - Frame shows "Install OSS" when disabled, pill when enabled.
  - CLI block expands / collapses; emits correct command text.
  - Install modal lists tools in expected order.
  - Domain card folds + shows finding counts by severity.
- Shape-only assertions forbidden — verify semantic content (icons, text labels, button states).

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — pass.
2. `make lint` — pass (Jinja templates are checked by `make lint` via the project's JS/YAML linter? confirm per CLAUDE.md).

## Subagent Result Contract

Standard JSON.
