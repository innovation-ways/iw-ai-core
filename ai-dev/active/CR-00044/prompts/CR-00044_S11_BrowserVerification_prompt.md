# Browser Verification Prompt: CR-00044-S11-BrowserVerification

**Work Item**: CR-00044 -- Markdown viewer for subdirectory docs, sharper per-page help-doc mappings, and favicon route
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

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:9900`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment.

Do NOT hardcode application **route paths** either. Routes drift; a stale path fails with a 404 that *looks* like a code defect but is a spec mismatch. Where a UI path exists, navigate via the UI (open a list/index page and click through) exactly as a user would. For this CR the routes under test (`/system/docs/...`, `/favicon.ico`, the help popovers) are stable, but still confirm each page **loaded successfully** (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors) before asserting on its content. A 500 on the page containing the element you're verifying is itself a `code_defect` finding.

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose up/down/restart/build` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/CR-00044/CR-00044_CR_Design.md` -- the design document
- `dashboard/app.py` -- `GET /favicon.ico` route
- `dashboard/routers/system.py` -- `GET /system/docs/{doc_path:path}` route
- `dashboard/routers/help.py` -- `_SLUG_TO_DOC` retargeting
- `dashboard/templates/pages/system/docs_view.html` -- docs viewer page (title wiring)
- `dashboard/CLAUDE.md` -- routers-table note
- `tests/dashboard/test_system_docs_route.py`, `tests/dashboard/test_help_router.py`, `tests/dashboard/test_favicon.py` -- tests

## Output Files

- `ai-dev/active/CR-00044/reports/CR-00044_S11_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00044/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot                       # get accessible element refs (e10, e12, ...)
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00044/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB via `pg_dump`. This CR's behaviour does **not** depend on any seeded rows — the docs viewer reads `.md` files from the worktree's source tree, the help popovers are static templates, and `/favicon.ico` is a static asset. No `e2e_fixtures` file should be needed. If you nonetheless hit a missing-data wall, follow the standard `ENV_DATA_MISSING:` path (add a fixture under `ai-dev/active/CR-00044/e2e_fixtures/NNN_<name>.py`, re-run the seed inside the `app` container, never from the host).

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

The qv-browser agent automatically visits every distinct page route referenced in V1..V(n), extracts fragment references (`hx-target`, `hx-include`, `aria-controls`, `aria-labelledby`, `href="#X"`, `for=`) from the rendered HTML, verifies each referenced `id` exists in the same response, and reads `.playwright-cli/console-*.log` after each load to detect unhandled JS/HTMX errors. Dangling references or load-time errors are a V0 FAIL. V1..V(n) still run if V0 fails; `overall_status` becomes `fail` and the V0 finding leads the `--reason`.

### V1: No `/favicon.ico` console error on a dashboard page

1. Navigate to `$IW_BROWSER_BASE_URL/` (the projects landing page), then to one project page (open the project list and click any project's "Queue" link).
2. After each page settles, read `.playwright-cli/console-*.log` for that session — the change makes the browser's automatic `GET /favicon.ico` succeed instead of 404, so there should be **zero** console errors on these pages (the `/favicon.ico` 404 was the only one pre-change). Also directly check the asset: `curl -s -o /dev/null -w '%{http_code} %{content_type}\n' "$IW_BROWSER_BASE_URL/favicon.ico"` must print `200 image/svg+xml...`.
3. **Verify:** the queue page loaded HTTP 200, and the console log for the session shows no errors (in particular nothing mentioning `favicon.ico`).
4. **Screenshot:** `ai-dev/active/CR-00044/evidences/post/CR-00044_v1_favicon_no_console_error.png`.

### V2: Code-page help popover opens the RAG documentation

1. Navigate to a project's Code page (open the project, then its "Code" page from the nav).
2. `playwright-cli snapshot`, find the "Help for this page" button (`data-help-slug="code"`), click it — this opens the contextual help popover for the Code page.
3. `playwright-cli snapshot` the open popover, find the "Open full docs →" link, confirm its `href` is `/system/docs/orch/rag/CLAUDE.md` (optionally with a `#fragment`). Click it.
4. **Verify:** the browser navigates to `$IW_BROWSER_BASE_URL/system/docs/orch/rag/CLAUDE.md`, the page loads HTTP 200 inside the dashboard chrome (sidebar + search bar), and the rendered body shows content from `orch/rag/CLAUDE.md` (e.g. a heading present in that file). No console errors.
5. **Screenshot:** `ai-dev/active/CR-00044/evidences/post/CR-00044_v2_code_help_opens_rag_doc.png`.

### V3: Item-detail / Research / Search help popovers point at the Dashboard Design doc

1. For each of: an Item Detail page (open the project's History, click an item row), the Research page, and the Search page — open the "?" help popover.
2. In each popover, read the "Open full docs →" link `href`.
3. **Verify:** each `href` is `/system/docs/IW_AI_Core_Dashboard_Design` (optionally `#fragment`); pick one of them, click it, and confirm the target loads HTTP 200 with rendered content from `docs/IW_AI_Core_Dashboard_Design.md`. (Spot-check that the Projects page help still points at `/system/docs/IW_AI_Core_Architecture` — unchanged.)
4. **Screenshot:** `ai-dev/active/CR-00044/evidences/post/CR-00044_v3_dashboard_design_links.png`.

### V4: Subdirectory document renders; traversal is rejected

1. Navigate directly to `$IW_BROWSER_BASE_URL/system/docs/implementation/00_INDEX`.
2. **Verify:** HTTP 200, dashboard chrome present, rendered content from `docs/implementation/00_INDEX.md`, and the page `<title>` reflects that file's first H1 (not the literal string `implementation/00 INDEX`). Then check rejection: `curl -s -o /dev/null -w '%{http_code}\n' "$IW_BROWSER_BASE_URL/system/docs/../README"` and `.../system/docs/orch/config.py` must both print `404`. Also confirm a flat-form URL still works: `$IW_BROWSER_BASE_URL/system/docs/IW_AI_Core_Daemon_Design` → 200.
3. **Screenshot:** `ai-dev/active/CR-00044/evidences/post/CR-00044_v4_subdir_doc_and_traversal.png`.

### V5: No Regressions

1. Re-open two or three help popovers on pages whose mappings did NOT change (`queue` → `/system/docs/IW_AI_Core_CLI_Spec#iw-approve`, `batches` → `/system/docs/IW_AI_Core_Daemon_Design`, `status` → `/system/docs/IW_AI_Core_DB_Setup`); confirm each "Open full docs →" link still resolves to HTTP 200 and (for `queue`) scrolls to the `iw approve` section. Confirm the popover still shows its four sections and the "Take the 30-second tour →" button.
2. Verify no new console errors appeared on any page visited during V1..V4.
3. **Screenshot:** `ai-dev/active/CR-00044/evidences/post/CR-00044_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

### Distinguishing code defects from environment gaps and spec mismatches

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw console exception | CODE_DEFECT | normal `--reason` |
| Page rendered cleanly but element/data missing because seed lacks it | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` + add fixture |
| Page rendered cleanly, element correctly absent per design doc, V step asks for it anyway | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V{N} ..."` |
| Page rendered cleanly, design says element should be present, it isn't | CODE_DEFECT | normal `--reason` |

For this CR, ENV_DATA_MISSING is unlikely (no seeded data involved). A traversal URL that returns 200 instead of 404 is a **CODE_DEFECT** (security regression) — report it prominently.

## Report

After verification, write `ai-dev/active/CR-00044/reports/CR-00044_S11_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if you investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the unchanged help mappings and popover structure tested in V5.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00044/reports/CR-00044_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00044/reports/CR-00044_S11_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "CR-00044",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "No favicon console error", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Code help popover opens RAG doc", "status": "pass|fail|n/a", "failure_class": "...", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Item-detail/Research/Search links point at Dashboard Design doc", "status": "pass|fail|n/a", "failure_class": "...", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Subdir doc renders; traversal rejected", "status": "pass|fail|n/a", "failure_class": "...", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": "...", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
