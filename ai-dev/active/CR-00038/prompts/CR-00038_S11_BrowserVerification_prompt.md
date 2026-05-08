# Browser Verification Prompt: CR-00038-S11-BrowserVerification

**Work Item**: CR-00038 — Docs View: Filter Bar Redesign + Running-Jobs Strip + Spinner Fix
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures (they self-label and self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which commands are safe.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations in this CR. Do not run alembic against the live DB.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use `$IW_BROWSER_BASE_URL`. Do NOT run `make dev`, `docker compose up`, `playwright install`, `agent-browser`, or `chromium.launch()`.

## Input Files

- `ai-dev/active/CR-00038/CR-00038_CR_Design.md`
- `dashboard/templates/docs_library.html`
- `dashboard/templates/fragments/docs_running_jobs.html`
- `dashboard/routers/docs.py`

## Output Files

- `ai-dev/active/CR-00038/reports/CR-00038_S11_BrowserVerification_Report.md`
- `ai-dev/active/CR-00038/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in if a login page is shown:
```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Then navigate to the docs page for the first available project. Use `playwright-cli snapshot` before every `click` or `fill` to get current element refs.

## E2E DB Seed Data

The E2E stack's PostgreSQL is seeded from production via `pg_dump`. If verifications require a running DocGenerationJob that doesn't exist in production seed, add a fixture:

```
ai-dev/active/CR-00038/e2e_fixtures/001_running_job.py
```

Export `def seed(db: Session) -> None` — create a `DocGenerationJob` with `status=running` for an existing doc. Make it idempotent (`db.get(...)` before insert). After writing the fixture:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove)

> Automatically prepended by the qv-browser agent. Checks all fragment refs and load-time console errors.

### V1: Filter bar is a single row with two selects and a search input

1. Navigate to `$IW_BROWSER_BASE_URL/project/<first-project-id>/docs`.
2. Capture a snapshot to inspect the page structure.
3. **Verify:** The filter area contains a `<select>` element for Type and a `<select>` element for Status — no pill buttons with class `filter-pill` are present. A search text input is also present on the same row.
4. **Screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/CR-00038/evidences/post/CR-00038_v1_filter_bar.png`.

### V2: Type dropdown filters the grid

1. On the docs page, snapshot to find the Type select ref.
2. Select a specific doc type (e.g., "Architecture") from the Type dropdown — this triggers an htmx request to reload the grid.
3. Wait for the grid to update (snapshot again).
4. **Verify:** The grid shows only cards matching the selected type, or the empty-state message if none exist. No 5xx error in console.
5. **Screenshot:** `ai-dev/active/CR-00038/evidences/post/CR-00038_v2_type_filter.png`.

### V3: Status and Type filters combine

1. On the docs page with a type already selected, snapshot to find the Status select ref.
2. Select "Published" from the Status dropdown.
3. **Verify:** The grid now reflects both the Type and Status filter (both values sent in the same request). No pill markup visible.
4. **Screenshot:** `ai-dev/active/CR-00038/evidences/post/CR-00038_v3_combined_filters.png`.

### V4: Running-jobs strip appears and button is disabled after Generate click

1. Navigate to the docs page. Find a doc card with a Generate or Regenerate button.
2. If no such button exists in the seed data, add an e2e fixture to create a `planned` doc.
3. Click the Generate/Regenerate button.
4. **Verify:** The button is immediately replaced with a disabled grey button showing "Queued…" text. Below the filter bar, a running-jobs row appears showing the doc title and a spinner. Console shows no errors.
5. **Screenshot:** `ai-dev/active/CR-00038/evidences/post/CR-00038_v4_generate_queued.png`.

### V5: Running-jobs strip shows jobs that were already running on page load

1. Ensure a running DocGenerationJob exists in the DB (via seed fixture if needed).
2. Navigate (fresh load) to the docs page.
3. **Verify:** The running-jobs strip renders the in-progress job row without requiring any user interaction.
4. **Screenshot:** `ai-dev/active/CR-00038/evidences/post/CR-00038_v5_strip_on_load.png`.

### V6: No Regressions

1. Verify the stale-docs summary row still loads above the filter bar.
2. Verify the Settings gear icon still opens the config panel.
3. Verify the Select Mode toggle and export action bar still function.
4. Verify the card View and Export links are still present and clickable.
5. Check `.playwright-cli/console-*.log` for any new unhandled JS errors not present before this CR.
6. **Screenshot:** `ai-dev/active/CR-00038/evidences/post/CR-00038_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. Any failure requires `iw step-fail`. Classify as `CODE_DEFECT`, `ENV_DATA_MISSING`, or `SPEC_MISMATCH` per the standard classification table.

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00038/reports/CR-00038_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short reason>" \
  --report ai-dev/active/CR-00038/reports/CR-00038_S11_BrowserVerification_Report.md
```

## Report

Include:
- Pass/fail table for V1..V6
- `$IW_BROWSER_BASE_URL` value used
- Screenshots list
- No-regressions subsection

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "CR-00038",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Filter bar single row", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Type dropdown filters grid", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Combined type+status filters", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Generate queued — button disabled + strip row", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Strip shows in-progress jobs on page load", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No regressions", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
