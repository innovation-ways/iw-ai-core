# Browser Verification Prompt: I-00079-S11-BrowserVerification

**Work Item**: I-00079 -- Empty-state CTA links point to non-existent `/docs/<name>.md` route (404)
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
  4. `docker compose -p "$COMPOSE_PROJECT_NAME" exec app ...` to re-run the
     E2E seed after writing a fixture file (see "E2E DB seed data" below).

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

This item adds no migrations and touches no database schema — there is nothing
to apply. If your task seems to require applying a migration, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, no `localhost:3100`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment.

Do NOT hardcode application **route paths** for entity detail pages. **Navigate via the UI** wherever possible — open a list/index page (the project list `/`, a project's Queue / History / Batches, the Docs / Research library, the System "All Active Work" page) and click the empty-state panel's call-to-action link exactly as a user would. The page you land on is whatever that link resolves to — that is precisely what this item is verifying. The dashboard's doc-viewer pages (`/system/docs/<DocName>`) are also reachable from each page's contextual help popover ("Open full docs"); use that as a cross-check.

Before asserting on the *content* of any page, first confirm the page itself **loaded successfully** (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors). A page whose body is the JSON string `{"detail":"Not Found"}` is the **exact pre-fix failure** this item fixes — if you see that after clicking any empty-state CTA, the verification FAILS (`code_defect`).

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose up/down/restart/build` -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00079/I-00079_Issue_Design.md` -- the design document (Description's affected-templates table, AC1–AC3)
- `dashboard/templates/macros/empty_state.html` -- the empty-state panel macro (`<a href="..." class="empty-state__cta-primary">{{ primary_label }}</a>`)
- `dashboard/templates/pages/project/queue.html`, `dashboard/templates/pages/project/history.html`, `dashboard/templates/pages/project/batches.html`, `dashboard/templates/pages/system/all_active.html`, `dashboard/templates/docs_library.html`, `dashboard/templates/research_library.html` -- the six fixed templates
- `dashboard/routers/system.py` -- the doc viewer (`/system/docs/{doc_path:path}` under the `/system` prefix)
- `dashboard/routers/help.py` -- `_SLUG_TO_DOC` (the help-popover "Open full docs" targets, used as a cross-check)
- `ai-dev/active/I-00079/evidences/pre/I-00079-broken-link-404.png` -- pre-fix reference: the `{"detail":"Not Found"}` page

## Output Files

- `ai-dev/active/I-00079/reports/I-00079_S11_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/I-00079/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials if a login screen appears:

```bash
playwright-cli snapshot                       # get accessible element refs (e10, e12, ...)
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

(If the E2E stack has no login screen — it may go straight to the dashboard — skip the login step and proceed.)

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00079/evidences/post/` with descriptive filenames (`playwright-cli screenshot` writes to `.playwright-cli/page-*.png`; then `cp .playwright-cli/page-*.png ai-dev/active/I-00079/evidences/post/<name>.png`).
4. To read the *rendered HTML* of a page (e.g. to extract the `empty-state__cta-primary` `href` before clicking it), `curl -s "<page-url>"` is fine for unauthenticated routes; for authenticated routes use the browser snapshot, which shows the link's `/url:` target.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB
via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`). It reflects
current production state.

The empty-state panels only render when a list is **empty**. Production usually
has at least one project with no work items, no batches, and no docs (e.g. a
freshly-registered project) — that project's Queue, History, Batches, Docs, and
Research pages all show the empty-state panel with the CTA. Browse the project
list (`$IW_BROWSER_BASE_URL/`) and pick such a project. The `/system/all-active`
page shows its empty state only when there is no active work anywhere — if there
IS active work in the seed, treat the all-active CTA as covered by the
help-popover cross-check in V4 instead, and note it.

If **no** project has an empty Queue/History/Batches/Docs/Research in the seed,
add a fixture that registers a brand-new empty project:

```
ai-dev/active/I-00079/e2e_fixtures/001_empty_project.py
```

The file must export `def seed(db: Session) -> None`, be idempotent (`db.get(...)`
/ `db.query(...).filter(...)` before insert), and create one `Project` row with no
related `WorkItem` / `Batch` / doc rows. Then re-run the seed inside the `app`
container before opening the browser:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run the seed from your host shell.** The host's `.env` resolves to the
> production orchestration DB on port 5433 — running `scripts/e2e_seed.py` outside
> a container writes test rows into the real DB. If `docker compose exec` fails
> (container unreachable), call `iw step-fail` with `ENV_DATA_MISSING:` so the
> daemon re-provisions the stack.

Do not write "blocked — n/a" chains. If a precondition is missing, create it (fixture file → re-seed), then proceed.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

> This verification is automatically prepended by the qv-browser agent before any work-item-specific V steps. It is documented here so design reviewers know what runs.

The agent visits every distinct page route referenced in V1..V(n) and:

- Extracts all fragment references (`hx-target="#X"`, `hx-include="#X"`, `aria-controls="X"`, `aria-labelledby="X"`, `href="#X"`, `for="X"`) from the rendered HTML via `curl`.
- Verifies each referenced `id="X"` is present in the same HTML response.
- Reads `.playwright-cli/console-*.log` after each page load to detect unhandled JS or HTMX errors.
- Flags any dangling reference or unhandled load-time error as a V0 FAIL.

**If V0 fails, V1..V(n) still run.** `overall_status` is `fail` and the V0 finding appears first in the `--reason`.

### V1: "How to design an item →" on an empty Queue opens the CLI-spec doc, not a 404 (AC1 — the reported bug)

1. From `$IW_BROWSER_BASE_URL/`, pick a project whose **Queue** is empty (no approved items, no drafts) and open its Queue page via the sidebar.
2. In the "No work items yet" panel, read the **"How to design an item →"** link's target from the snapshot — it must be `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` (or at least start with `/system/docs/IW_AI_Core_CLI_Spec`); it must **not** be `/docs/IW_AI_Core_CLI_Spec.md` and must not end in `.md`.
3. Click the link. The page that loads must be the **CLI-spec documentation page** rendered in the normal dashboard chrome (a heading derived from the doc's H1, the doc body as HTML — headings, tables, code blocks). It must **NOT** be the bare JSON body `{"detail":"Not Found"}` and must **NOT** be an HTTP error / exception page.
4. **Verify:** the CTA's target is the `/system/docs/IW_AI_Core_CLI_Spec...` form; clicking it renders the CLI-spec doc page (HTTP 200, doc content visible); no load-time console errors.
5. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00079/evidences/post/I-00079_v1_queue_cta_opens_cli_spec.png`.

### V2: "How execution works →" on an empty History opens the Architecture doc (AC1)

1. Open the same (or another) empty-history project's **History** page via the sidebar.
2. In the empty-state panel, the **"How execution works →"** link's target must start with `/system/docs/IW_AI_Core_Architecture` (no `.md`, no bare `/docs/`).
3. Click it — the **Architecture documentation page** must render (heading + doc body), not `{"detail":"Not Found"}`, not an error page.
4. **Verify:** CTA target is `/system/docs/IW_AI_Core_Architecture`; clicking renders the Architecture doc (HTTP 200); no console errors.
5. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00079/evidences/post/I-00079_v2_history_cta_opens_architecture.png`.

### V3: "About batches →" on an empty Batches page opens the Daemon-Design doc (AC1)

1. Open an empty-batches project's **Batches** page via the sidebar.
2. The **"About batches →"** link's target must start with `/system/docs/IW_AI_Core_Daemon_Design` (an `#batches` anchor may follow; no `.md`, no bare `/docs/`).
3. Click it — the **Daemon-Design documentation page** must render (heading + doc body), not a 404 JSON / error page. If the page has a `batches` section heading and the browser jumps to it, note that; if not, the page still must render fine — the anchor is best-effort.
4. **Verify:** CTA target is `/system/docs/IW_AI_Core_Daemon_Design...`; clicking renders the Daemon-Design doc (HTTP 200); no console errors.
5. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00079/evidences/post/I-00079_v3_batches_cta_opens_daemon_design.png`.

### V4: Docs-library, Research-library, and All-Active-Work CTAs open real doc pages (AC1, AC3)

1. **Docs library** — open an empty-docs project's **Docs** page via the sidebar. The empty-state **"Doc catalogue →"** link's target must start with `/system/docs/implementation/00_INDEX` (this exercises CR-00044's subdirectory doc serving — no `.md`, no bare `/docs/`). Click it — the **implementation index** doc page must render (heading + doc body), not `{"detail":"Not Found"}`. (If `/system/docs/implementation/00_INDEX` 404s, that is a `code_defect` — the subdirectory doc route isn't serving it; report it.)
2. **Research library** — open the same project's **Research** page. The empty-state **"Open the catalogue →"** link must also point at `/system/docs/implementation/00_INDEX` and clicking it must render the implementation-index doc page (HTTP 200).
3. **All Active Work** — open `/system/all-active` (System → All Active Work). If it shows the empty-state panel ("No active work" or similar), the **"Daemon overview →"** link must start with `/system/docs/IW_AI_Core_Daemon_Design` and clicking it must render the Daemon-Design doc page. If the seed has active work so the empty state does NOT render, instead open this page's contextual **help popover** ("?") and click its **"Open full docs"** link — it must also resolve to a `/system/docs/...` doc page (HTTP 200), confirming the doc-viewer route works for this page; note in the report that the all-active empty-state CTA itself wasn't exercised because the list was non-empty (this is acceptable — it's the same `primary_href` string the unit test in `tests/dashboard/test_empty_states.py` checks).
4. **Verify:** each CTA target uses the `/system/docs/...` form (no `.md`); each click renders a real doc page (HTTP 200); no console errors. Note explicitly whether the all-active empty state was reachable.
5. **Screenshot:** one per sub-step where feasible — `cp .playwright-cli/page-*.png ai-dev/active/I-00079/evidences/post/I-00079_v4_docs_index_opens.png` (and `..._v4_research_index_opens.png`, `..._v4_all_active.png`).

### V5: No regressions

1. Confirm the doc-viewer pages reached in V1..V4 render with the normal app chrome (sidebar, top search bar, footer all present) — they're not blank or broken.
2. On at least two of the pages that have a contextual help popover (Queue, History, Batches, All Active Work), open the "?" help popover and confirm its **"Open full docs"** link still works (it's the pre-existing CR-00042/CR-00044 behaviour — must still resolve to a `/system/docs/...` doc page, HTTP 200). The empty-state CTA and the help popover for the same page should land on the same (or a closely related) doc.
3. Navigate between a couple of ordinary pages (a project Dashboard, the project list `/`, a `/system/*` page) — each renders cleanly with no new console errors.
4. Verify no new console errors appeared on any page visited during V1..V4.
5. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00079/evidences/post/I-00079_v5_no_regressions.png`.

## Pass Criteria

All V1..V(n) must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

### Distinguishing code defects from environment gaps and spec mismatches

| Failure shape | Class | Action |
|---|---|---|
| Clicking a CTA shows `{"detail":"Not Found"}` / 5xx / a console exception | CODE_DEFECT | normal `--reason` |
| `/system/docs/implementation/00_INDEX` returns 404 (subdir doc route not serving it) | CODE_DEFECT | normal `--reason` |
| Page rendered cleanly but no project has an empty Queue/History/Batches/Docs/Research and you couldn't add a fixture | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` + add `e2e_fixtures/001_empty_project.py` |
| Page rendered cleanly, the CTA target is correct (`/system/docs/...`), but a V step asks for something the design says shouldn't be there | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V{N} ..."` citing the design doc |

- **CODE_DEFECT** -- a CTA still 404s, a doc page errors, or a doc page that should resolve doesn't. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** -- the dashboard rendered fine (HTTP 200) but no empty-state panel was reachable because every project has data. The fix-cycle agent **cannot** fix this by editing code; add the empty-project fixture and re-seed. Prefix the reason with `ENV_DATA_MISSING:` and name the fixture path. The fix path is to add the fixture, not to retry.
- **SPEC_MISMATCH** -- the implementation is correct, the V step's expectation is wrong. Prefix with `SPEC_MISMATCH:` and cite the design doc location. The fix-cycle agent MUST NOT attempt code patches for SPEC_MISMATCH.

### No cascading `n/a` — seed on demand

Work item authors MUST NOT write "blocked by V1 — n/a" chains. The agent is responsible for creating missing preconditions itself: (1) use a UI path the implementation provides; (2) add/extend `ai-dev/active/I-00079/e2e_fixtures/NNN_<name>.py` and re-run the seed inside the app container; (3) write the row directly via the per-worktree DB if the design supplies the SQL. A run with one `fail` and four `n/a` is a workflow defect, not a valid report.

## Report

After verification, write `ai-dev/active/I-00079/reports/I-00079_S11_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V0..V(n).
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- For each CTA exercised: the page it was on, the link's `/url:` target, and the page that loaded after clicking.
- Any issues found, with `file:line` references if you investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the help-popover links and adjacent pages tested in V5.
- Whether an `e2e_fixtures` file was added (and why), and whether the all-active empty state was reachable.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00079/reports/I-00079_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00079/reports/I-00079_S11_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00079",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "<the concrete $IW_BROWSER_BASE_URL>",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Queue CTA opens CLI-spec doc, not 404", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "History CTA opens Architecture doc", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Batches CTA opens Daemon-Design doc", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Docs/Research/All-Active CTAs open real doc pages", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed or was legitimately `n/a`. `fail` on any failure.
- `overall_failure_class`: the most severe failure class observed. Severity order for human routing: `spec_mismatch` > `env_data_missing` > `code_defect`. `null` when `overall_status` is `pass`.
- `failure_class` per verification: `null` when status is `pass` or `n/a`.
- `base_url_used`: the concrete URL the agent actually hit -- confirms the worktree stack (not the dev server) was tested.
- `console_errors_observed`: any console errors seen during any V(n), even on an otherwise-passing run.
