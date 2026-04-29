# Browser Verification Prompt: {{ID}}-{{STEP}}-BrowserVerification

**Work Item**: {{ID}} -- {{TITLE}}
**Step**: {{STEP}}
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

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/{{ID}}/{{ID}}_{{TYPE}}_Design.md` -- the design document
- {{LIST_OF_FILES_MODIFIED_BY_IMPLEMENTATION_STEPS}}
  - e.g. `frontend/src/components/foo/Bar.tsx`
  - e.g. `frontend/src/pages/Baz.tsx`

## Output Files

- `ai-dev/active/{{ID}}/reports/{{ID}}_{{STEP}}_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/{{ID}}/evidences/post/` -- screenshots taken during verification

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
3. Screenshots go under `ai-dev/active/{{ID}}/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB
via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`). It reflects
current production state. It does **not** contain data that only exists in
`scripts/e2e_seed.py`'s baseline unless that script has been explicitly run.

If your verifications require data not yet in production (e.g. a new document
type, diagram rows, or specific work-item history), add a fixture file:

```
ai-dev/active/{{ID}}/e2e_fixtures/001_<descriptive_name>.py
```

The file must export `def seed(db: Session) -> None`. Make it idempotent
(`db.get(...)` before insert). Multiple files load in lexical order; use
`001_`, `002_`, … prefixes.

**After writing a fixture file you MUST re-run the seed inside the `app`
container before opening the browser.** The worktree directory is already
mounted at `/workspace` inside the container, so any file you write on the
host is immediately visible. Run:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
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

Replace the V1..V(n) below with concrete, per-acceptance-criterion verifications derived from the feature design. Each verification must state:

1. **What to navigate to** -- a route under `{{IW_BROWSER_BASE_URL}}` (the platform substitutes this placeholder with the concrete base URL at launch time, so the LLM sees a real URL).
2. **What to click or type** -- with a one-sentence rationale explaining why that interaction triggers the feature.
3. **What to verify** -- exact text, element visibility, URL change, or the absence of console errors.
4. **Capture an evidence screenshot:** `playwright-cli screenshot` (no path argument — saves to `.playwright-cli/page-<ts>.png`), then `cp .playwright-cli/page-*.png ai-dev/active/{{ID}}/evidences/post/{{ID}}_v{N}_{{short_name}}.png`. Passing a path to `playwright-cli screenshot` is invalid — the tool treats it as a page element ref and errors.

### V1: {{one-line description of the primary user-visible feature}}

1. Navigate to `{{IW_BROWSER_BASE_URL}}/{{specific_route}}`.
2. {{interaction -- e.g. "click the 'New Batch' button in the top-right toolbar"}} -- this {{rationale}}.
3. **Verify:** {{observable outcome -- e.g. "a modal titled 'Create Batch' is visible and contains a 'Name' input and a 'Create' button"}}.
4. **Screenshot:** `ai-dev/active/{{ID}}/evidences/post/{{ID}}_v1_{{short_name}}.png`.

### V2: {{secondary check}}

1. {{Navigate}}.
2. {{Interact}}.
3. **Verify:** {{outcome}}.
4. **Screenshot:** `ai-dev/active/{{ID}}/evidences/post/{{ID}}_v2_{{short_name}}.png`.

{{Add V3, V4, ... as needed -- one per acceptance criterion in the design doc.}}

### V(n): No Regressions

1. Revisit the buttons/flows adjacent to the changed code and verify they still behave correctly.
2. Verify no new console errors appeared on any page visited during V1..V(n-1).
3. **Screenshot:** `ai-dev/active/{{ID}}/evidences/post/{{ID}}_v{{n}}_no_regressions.png`.

## Pass Criteria

All V1..V(n) must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

### Distinguishing code defects from environment gaps

Before failing the step, classify the failure:

- **CODE DEFECT** -- the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** -- the page rendered cleanly with HTTP 200 but showed an empty-state message ("No items yet", "No retries — clean run", "0 results") because the E2E DB lacks the historical rows the verification expects. The fix-cycle agent **cannot** fix this by editing code; it needs an `e2e_fixtures` file. Prefix the reason with `ENV_DATA_MISSING:` so the daemon recognises the class:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V1 expects F-00055 step_runs (S13×3, S10×2) — add ai-dev/active/{{ID}}/e2e_fixtures/001_f00055_history.py" \
    --report ai-dev/active/{{ID}}/reports/{{ID}}_{{STEP}}_BrowserVerification_Report.md
  ```

  The reason is for the human reviewer; the fix path is to add a fixture, not to retry.

## Report

After verification, write `ai-dev/active/{{ID}}/reports/{{ID}}_{{STEP}}_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V(n).
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V(n).

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/{{ID}}/reports/{{ID}}_{{STEP}}_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/{{ID}}/reports/{{ID}}_{{STEP}}_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "{{STEP}}",
  "agent": "qv-browser",
  "work_item": "{{ID}}",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed. `fail` on any failure.
- `base_url_used`: The concrete URL the agent actually hit -- used by reviewers to confirm the worktree stack (not the dev server) was tested.
- `console_errors_observed`: Any console errors seen during any V(n), even if the verification otherwise passed. A non-empty list on a passing run should be flagged in the report.
