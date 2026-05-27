# Browser Verification Prompt: F-00090-S16-BrowserVerification

**Work Item**: F-00090 -- Regression-rate tracking — correlate filed Incidents back to the merge that introduced the regression
**Step**: S16
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

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:3100`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment (often the dev server serving `main` branch instead of your feature worktree).

Do NOT hardcode application **route paths** either (e.g. `/project/{id}/work/{item}` vs `/project/{id}/item/{item}`). Routes drift; a stale path in a verification prompt fails with a 404 that *looks* like a code defect but is a spec mismatch. Prefer to **navigate via the UI** — open a list/index page (`/history`, `/batches`, the project home) and click the link/row for the entity under test, exactly as a user would. The detail-page URL the app actually uses is whatever that link resolves to. Only fall back to a direct URL when no UI path exists, and when you do, treat any 404 as "the prompt's URL is wrong" (`spec_mismatch`), not a code defect — and report the corrected path.

Before asserting on the *content* of any page, first confirm the page itself **loaded successfully** (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors). A 500 on the page that contains the element you're verifying is itself a `code_defect` finding — capture the server traceback (it's usually in the response body or the app container logs) and report it; do not retry the same navigation expecting a different result.

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/F-00090/F-00090_Feature_Design.md` -- the design document
- `dashboard/routers/items.py`
- `dashboard/routers/batches.py`
- `dashboard/routers/project_dashboard.py`
- `dashboard/templates/fragments/regression_classification_form.html`
- `dashboard/templates/fragments/regression_suggestion_list.html`
- `dashboard/templates/fragments/quality_kpis_section.html`
- `dashboard/templates/fragments/regression_badge.html`
- `dashboard/templates/pages/quality_kpis.html`
- `dashboard/static/styles.css`
- `orch/regression_link_service.py`

## Output Files

- `ai-dev/active/F-00090/reports/F-00090_S16_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/F-00090/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
# Clear accumulated console logs from prior fix-cycle browser sessions so that
# V5's console-error check only inspects logs from THIS run, not stale ones.
rm -f .playwright-cli/console-*.log
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
3. Screenshots go under `ai-dev/active/F-00090/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB
via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`). It reflects
current production state. It does **not** contain data that only exists in
`scripts/e2e_seed.py`'s baseline unless that script has been explicitly run.

If your verifications require data not yet in production (e.g. a new document
type, diagram rows, or specific work-item history), add a fixture file:

```
ai-dev/active/F-00090/e2e_fixtures/001_<descriptive_name>.py
```

The file must export `def seed(db: Session) -> None`. Make it idempotent
(`db.get(...)` before insert). Multiple files load in lexical order; use
`001_`, `002_`, … prefixes.

**For this feature you almost certainly need fixtures** for V2..V4 (you need
at least one merged work item AND one Incident classified as a regression
pointing to it, so the KPI shows non-zero numbers and the badge has something
to count). Create:

- `ai-dev/active/F-00090/e2e_fixtures/001_seed_merged_feature.py` — inserts (or upserts) a merged Feature F-Y so the badge has a target.
- `ai-dev/active/F-00090/e2e_fixtures/002_seed_classified_incident.py` — inserts (or upserts) an Incident I-X with `introduced_by_work_item_id=F-Y`, `regression_classification='regression'`, `classified_by='operator:sergiog'`, `classified_at=now()`.

**After writing a fixture file you MUST re-run the seed inside the `e2e-dashboard`
container before opening the browser.** The worktree `ai-dev/` directory is
already mounted at `/app/ai-dev` inside the container, so any fixture file you
write on the host is immediately visible. Run:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard \
  uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run the seed from your host shell.** The host's `.env`
> resolves to the production orchestration DB on port 5433 — running
> `uv run python scripts/e2e_seed.py` outside a container will write test
> rows into the real DB.
>
> Only if `docker compose exec` fails (container unreachable) should you
> call `iw step-fail` with `ENV_DATA_MISSING:` so the daemon
> re-provisions the stack.

If your verifications can't be satisfied with seed data alone (e.g. they
require a live agent run), call `iw step-fail` with reason prefixed
`ENV_DATA_MISSING:` (see Pass Criteria) — the daemon recognises this as
an environment gap, not a code defect, and skips the fix cycle.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

> Automatically prepended by the qv-browser agent. Visits every distinct
> page route referenced in V1..V(n), extracts fragment references, verifies
> ids are present, and checks `.playwright-cli/console-*.log` for unhandled
> JS/HTMX errors. V0 failure does not skip V1..V(n).

### V1: Classification form renders on an Incident detail page

1. Navigate to the project home (`{{IW_BROWSER_BASE_URL}}/`), click into the project, then navigate via the UI's Incidents/History list to an existing Incident (e.g., I-X seeded above). Prefer clicking the row over typing a URL.
2. Snapshot the page and confirm the **Regression classification** form section is visible — it must contain a searchable dropdown for the introducing work item, a free-text commit-SHA input, and a radio group with three labels (regression, pre-existing, unknown). This is the primary AC5 evidence.
3. **Verify:** all three radios are present, the searchable input has placeholder text, and the form's submit button is enabled.
4. **Screenshot:** `playwright-cli screenshot` (no path arg), then `cp .playwright-cli/page-*.png ai-dev/active/F-00090/evidences/post/F-00090_v1_classification_form.png`.

### V2: Quality KPIs section shows at least one classified regression

1. Navigate from the project home to the per-project home or directly to the project home page (via the UI). Confirm the **Quality KPIs** section is visible. Then click through to `/project/{pid}/quality-kpis` (or the link that resolves there).
2. Snapshot and verify the section shows three numbers (merges/week, regressions/week, rate) and an inline `<svg>` trend chart. The seeded classification from the fixture means `regressions/week >= 1` for the seeded week.
3. **Verify:** the SVG element exists, the page response contains `<svg`, the rate string is formatted as a number (not "NaN"), and at least one week-row shows a non-zero regression count.
4. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/F-00090/evidences/post/F-00090_v2_quality_kpis_section.png`.

### V3: Regression badge appears on Batches/History row

1. Navigate via the UI to the Batches or History page where merged items are listed. Locate the row for the seeded merged Feature F-Y.
2. Snapshot and verify the row carries a small badge (e.g. text "1 regressions") because the seeded Incident I-X points to F-Y.
3. **Verify:** the badge element with class `iw-regression-badge` exists on the F-Y row, and the visible count matches the number of classified Incidents pointing to F-Y (1 in the seeded case).
4. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/F-00090/evidences/post/F-00090_v3_regression_badge.png`.

### V4: Empty-state for a project with no merges

1. Navigate to a project that has no merged items (or pick a project URL the seed leaves empty). If no such project exists, this V is `n/a` with a one-line justification "no zero-merge project in seed data; AC6 zero-merge guard covered by unit test test_kpis_rate_is_zero_when_merges_zero".
2. **Verify:** the Quality KPIs section renders without crashing, rate reads "0.0" or equivalent, no JavaScript error in `.playwright-cli/console-*.log`.
3. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/F-00090/evidences/post/F-00090_v4_empty_state.png`.

### V5: No Regressions

1. Revisit the buttons/flows adjacent to the changed code and verify they still behave correctly:
   - The existing throughput KPI on the per-project home still renders.
   - The existing Incident detail page sections (status, design content, step list) still render.
   - The Batches/History rows that have NO regressions classified against them show NO badge.
2. Verify no new console errors appeared on any page visited during V1..V4. Read `.playwright-cli/console-*.log` for each.
3. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/F-00090/evidences/post/F-00090_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass (or V4 may be `n/a` if no zero-merge project is in the seed). Any failure — including partial or ambiguous — requires calling `iw step-fail` with a reason. There is no "mostly passed".

### Distinguishing code defects from environment gaps and spec mismatches

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw console exception | CODE_DEFECT | normal `--reason` |
| Page rendered cleanly but element/data missing because seed lacks it | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` + add fixture |
| Page rendered cleanly, element correctly absent per design doc, V step asks for it anyway | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V{N} ..."` |
| Page rendered cleanly, design says element should be present, it isn't | CODE_DEFECT | normal `--reason` |

### No cascading `n/a` — seed on demand

You are responsible for creating missing preconditions yourself via the e2e_fixtures mechanism above. Do not chain `n/a` failures.

## Report

After verification, write `ai-dev/active/F-00090/reports/F-00090_S16_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if you investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V5.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00090/reports/F-00090_S16_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00090/reports/F-00090_S16_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "F-00090",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Classification form renders on Incident detail page", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Quality KPIs section shows at least one classified regression", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Regression badge appears on Batches/History row", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Empty-state for a project with no merges", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
