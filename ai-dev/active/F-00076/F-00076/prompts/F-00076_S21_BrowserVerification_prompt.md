# Browser Verification Prompt: F-00076-S21-BrowserVerification

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S21
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

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live orch DB.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:9900`). Always use the env var.

Do NOT run any of the following:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser`
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/F-00076/F-00076_Feature_Design.md`
- `ai-dev/active/F-00076/evidences/pre/` -- pre-feature screenshots for comparison
- `dashboard/templates/fragments/item_overview.html`
- `dashboard/templates/fragments/batch_items.html`
- `dashboard/templates/system/worktrees_table.html`

## Output Files

- `ai-dev/active/F-00076/reports/F-00076_S21_BrowserVerification_Report.md`
- `ai-dev/active/F-00076/evidences/post/` -- screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
playwright-cli snapshot
# log in if the dashboard requires it (E2E user/password from env)
```

Rules:

1. Always call `playwright-cli snapshot` before `fill` / `click` to get fresh refs.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/F-00076/evidences/post/`.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from production via `pg_dump`. Verifications need:

- At least two Feature `WorkItem` rows registered in the same project, each with non-empty `impacted_paths`. (Production seed should already have many such items after F-00076 backfill ran.)
- A `BatchItem` in `pending` status with a recent `item_held_for_scope` `DaemonEvent` for V3.

If V3's data is missing (no held item exists in the seed), add a fixture file `ai-dev/active/F-00076/e2e_fixtures/001_held_item.py` exporting a `seed(db)` function that:

- Inserts two batches in the test project.
- Sets one item to `executing` with overlapping `impacted_paths`.
- Sets the other item to `pending` with overlapping `impacted_paths`.
- Inserts a `DaemonEvent` of type `item_held_for_scope` for the pending item with `event_metadata` matching the design's payload shape.
- Idempotent: `db.get(...)` before insert.

Re-seed inside the `app` container after writing the fixture (do NOT run from the host shell — the host's `.env` points at the production orch DB on port 5433):

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

If that command fails, call `iw step-fail` with `ENV_DATA_MISSING:` prefix.

## Verification Steps

### V1: Item overview shows declared Impacted Paths

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/item/<some-feature-with-declared-paths>` (pick any Feature with `config.scope_extraction.source == "declared"`).
2. Locate the "Impacted Paths" section on the overview tab.
3. **Verify:** the section is visible, lists the globs declared in the design doc, and shows a green `declared` badge.
4. **Screenshot:** `ai-dev/active/F-00076/evidences/post/F-00076_v1_item_declared.png` (run `playwright-cli screenshot` then `cp .playwright-cli/page-*.png` to that path).

### V2: Item overview shows regex-fallback badge

1. Navigate to an item whose `config.scope_extraction.source == "regex_fallback"` (use F-00076's own backfilled item or another older item from the seed).
2. **Verify:** the "Impacted Paths" section shows the amber `auto` badge and the tooltip text "regex fallback — please verify in design doc" appears on hover/focus.
3. **Screenshot:** `ai-dev/active/F-00076/evidences/post/F-00076_v2_item_auto.png`.

### V3: Batch detail shows "Held: overlaps with..." indicator

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/batch/<batch-with-held-item>`.
2. Locate the held item row.
3. **Verify:** the row displays `🔒 Held: overlaps with I-NNNNN on <glob>` (or the equivalent emoji-free fallback). Verify the `aria-label` attribute summarizes the conflict for screen readers.
4. **Screenshot:** `ai-dev/active/F-00076/evidences/post/F-00076_v3_batch_held.png`.

### V4: Worktrees page shows in-flight scope tooltip

1. Navigate to `{{IW_BROWSER_BASE_URL}}/system/worktrees`.
2. Hover/focus on a row representing an in-flight item.
3. **Verify:** a tooltip appears listing the in-flight item's `impacted_paths` (up to 5 globs, "+N more" if longer).
4. **Screenshot:** `ai-dev/active/F-00076/evidences/post/F-00076_v4_worktrees_tooltip.png`.

### V5: Dark-mode legibility

1. Toggle dark mode (or open in a session that defaults to dark mode).
2. Re-visit each of V1..V4 briefly.
3. **Verify:** badges, tooltips, and held indicators are legible (sufficient contrast) in dark mode. No styling regression compared to `evidences/pre/`.
4. **Screenshot:** `ai-dev/active/F-00076/evidences/post/F-00076_v5_dark_mode.png` (one composite or one per view — describe in the report).

### V6: No Regressions

1. Visit the queue page, history page, batches list, jobs page, code page, docs page. Confirm each renders without console errors.
2. Verify no new console errors appeared on any page visited during V1..V5.
3. Confirm the existing `Depends on / Blocks` panel on item overview still renders (the new "Impacted Paths" panel must not have displaced it).
4. **Screenshot:** `ai-dev/active/F-00076/evidences/post/F-00076_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** -- the page rendered the wrong element, threw a console error, or showed broken UI.
- **ENV_DATA_MISSING** -- HTTP 200 with empty-state and the seed lacks the rows V1/V2/V3/V4 expect (e.g. no held item exists). Add an `e2e_fixtures/` file as described above.

```bash
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "ENV_DATA_MISSING: V3 expects a pending item with item_held_for_scope event — add ai-dev/active/F-00076/e2e_fixtures/001_held_item.py" \
  --report ai-dev/active/F-00076/reports/F-00076_S21_BrowserVerification_Report.md
```

## Report

Write `ai-dev/active/F-00076/reports/F-00076_S21_BrowserVerification_Report.md` containing:

- Pass/fail table with one row per V1..V6.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references when investigated.
- The list of screenshots captured.
- A **No regressions observed** subsection.

Then call ONE of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00076/reports/F-00076_S21_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00076/reports/F-00076_S21_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S21",
  "agent": "qv-browser",
  "work_item": "F-00076",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "Item overview shows declared Impacted Paths", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Item overview shows regex-fallback badge", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Batch detail shows Held indicator", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Worktrees page shows in-flight scope tooltip", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Dark-mode legibility", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No Regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
