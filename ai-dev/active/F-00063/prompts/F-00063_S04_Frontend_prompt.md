# F-00063_S04_Frontend_prompt

**Work Item**: F-00063 -- Stale Process & Migration Detector
**Step**: S04
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network mutating commands. Read-only `docker ps`/`inspect`/`logs` and testcontainers in pytest fixtures are allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live orch DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00063/F-00063_Feature_Design.md`
- (S03 may run in parallel — read its prompt for the endpoint contract; do not block on its report)

## Output Files

- `ai-dev/active/F-00063/reports/F-00063_S04_Frontend_report.md`

## Context

You are building the dashboard UI for the Stale Process & Migration Detector. The dashboard uses Jinja2 templates + htmx (no React). All UI lives under `dashboard/templates/`.

Your job:
1. Three new template fragments (panel, dot, confirm dialog).
2. Wire them into the project home page and the project list page.
3. Auto-refresh both via `hx-trigger="every 15s"` so users never need to manually reload.

## Requirements

### 1. `dashboard/templates/fragments/staleness_panel.html`

Renders the full staleness panel for a single project. Receives a `staleness` context object shaped like `ProjectStalenessResult` (from S01).

Layout:

- If `staleness` is empty / has neither services nor alembic → render literally nothing (empty file output). The opt-out signal.
- Otherwise render a `<section>` with two sub-blocks:

  **Migrations** (rendered FIRST when `staleness.alembic` is present):
  - Status `up_to_date` → green check + "Database schema is up-to-date".
  - Status `stale` → red banner: "DB at `<current>`, code has `<head>` (`<N>` unapplied revisions)" + a `<ul>` listing each pending revision id and message + an "Upgrade head" button (POST `/projects/{id}/alembic/upgrade`).
  - Status `unreachable` → grey banner: "Cannot reach the database" with the error string in a `<details>` block. No upgrade button.
  - Status `no_config` → block omitted entirely.

  **Services**:
  - For each service render a row with: name (bold), status badge, start time (relative — "5 hours ago"), and (if status=stale) a collapsible list of commits-since-start (sha short + subject, one per line).
  - Status badges: `up_to_date` green, `stale` red, `not_running` grey, `hot_reload_skipped` blue, `unknown` grey.
  - Action buttons (only when applicable per `staleness.services[*].actions`):
    - `restart` in actions → `Restart` button → POST `/projects/{id}/services/{name}/restart`.
    - `start` in actions → `Start` button → POST `/projects/{id}/services/{name}/start`.
    - `stop` in actions → `Stop` button → POST `/projects/{id}/services/{name}/stop`.
  - Every action button uses `hx-confirm` set to a literal string OR (preferred) a custom modal triggered via `hx-target` that loads `staleness_confirm.html`. Pick the simplest pattern matching the existing dashboard conventions (search `dashboard/templates/fragments/` for `confirm_action.html` and reuse its style).
  - On 429 response, show a toast "Restart already in progress, try again in a few seconds".

- If BOTH alembic is `stale` AND any service is `stale`, render a hint copy at the top of the section: "Apply migrations first, then restart services."

The outer `<section>` element MUST include `hx-get="/projects/{id}/staleness"` `hx-trigger="every 15s"` `hx-swap="outerHTML"` so it self-refreshes.

### 2. `dashboard/templates/fragments/staleness_dot.html`

Tiny fragment for the project list row. Receives a `staleness` context (same shape).

- If `staleness.is_stale` → render `<span class="iw-staleness-dot iw-staleness-dot--red" title="Outdated processes — click for details"></span>`.
- Else if the project has services or alembic configured but everything's up-to-date → render `<span class="iw-staleness-dot iw-staleness-dot--grey"></span>` (informational; no warning).
- Else (opt-out) → render an empty body.

The `<span>` MUST include `hx-get="/projects/{id}/staleness-dot"` `hx-trigger="every 15s"` `hx-swap="outerHTML"`.

Add CSS for `.iw-staleness-dot` (small circle, ~10px, red `#dc2626` / grey `#9ca3af`) somewhere appropriate — look for existing global CSS files under `dashboard/static/` and reuse the conventions there.

### 3. `dashboard/templates/fragments/staleness_confirm.html`

Confirm dialog body. Receives `service_name`, `command_text`, and `action_url` in context.

- Title: "Confirm <action> of <service_name>"
- Body: shows the literal `command_text` in a `<code>` block.
- Buttons: "Cancel" (closes the modal) and "Confirm" (issues the POST via htmx and closes on response).

Match the existing modal style (look at `dashboard/templates/fragments/archive_batch_dialog.html` and `confirm_action.html` for reference).

### 4. Wire into project home

Edit `dashboard/templates/pages/project/dashboard.html`. Insert (somewhere appropriate near the top of the project content — find a good place that doesn't displace existing critical info) a `<div hx-get="/projects/{{ project.id }}/staleness" hx-trigger="load, every 15s" hx-swap="innerHTML">…loading…</div>` placeholder. The endpoint returns the panel fragment, which itself self-refreshes — so this initial wrapper just bootstraps the load.

### 5. Wire into project list

Find the template that renders the project list at `/` (start at `dashboard/routers/projects.py:370` to confirm the template name; likely `dashboard/templates/pages/project_selector.html` or similar). For each project row/card, insert at an appropriate visual location (next to the project name) a placeholder `<span hx-get="/projects/{{ p.id }}/staleness-dot" hx-trigger="load, every 15s" hx-swap="outerHTML"></span>`.

### 6. No backwards-compat / fallback for old browsers

Assume htmx is available (it's already a dashboard-wide dependency). No JS/no-JS toggle.

### 7. TDD: tests where they make sense

Frontend testing is template-rendering tests. Add a test per fragment in `tests/dashboard/test_staleness_templates.py` that renders the fragment with a hand-crafted context and asserts on key strings (status badges, button presence, htmx attributes). Use `Jinja2Templates` directly via the app instance.

## Project Conventions

- Look at existing fragments in `dashboard/templates/fragments/` for layout, class naming, htmx patterns.
- The dashboard CSS lives under `dashboard/static/` — match existing class naming (likely `iw-` prefixed).
- Match the existing colour palette (greys, reds, blues — find them in CSS variables before hardcoding hex values).
- Templates use Jinja2 (not Jinja3/-async); follow `{% if %}` `{% for %}` style consistent with the codebase.

## TDD Requirement

Red-Green-Refactor.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` (template-rendering tests live under `tests/dashboard/` and run as part of unit tests — this project has no separate `test-frontend` target)
2. `make lint` (covers JS in `dashboard/static/**/*.js` via `node --check`)
3. `make typecheck`

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "frontend-impl",
  "work_item": "F-00063",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
