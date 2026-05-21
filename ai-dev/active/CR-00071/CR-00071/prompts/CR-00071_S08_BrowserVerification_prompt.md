# Browser Verification Prompt: CR-00071-S08-BrowserVerification

**Work Item**: CR-00071 -- Pi Runtime Context-Usage Percentage Support
**Step**: S08
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

- `ai-dev/active/CR-00071/CR-00071_CR_Design.md` -- the design document
- `dashboard/routers/chat.py` -- the modified chat router (`get_tab` Pi branch injects `context_pct`)
- `orch/chat/context_usage.py` -- pure context-usage helpers (possibly extended with a Pi token normalizer)
- `dashboard/static/chat_assistant/chat.js` -- the CR-00067 frontend that consumes `session.context_pct` (NOT modified by this CR — verified for no regression)
- `dashboard/templates/chat_assistant/composer.html` -- the CR-00067 footer with the `#chat-assistant-context-pct` element (NOT modified by this CR)

## Output Files

- `ai-dev/active/CR-00071/reports/CR-00071_S08_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00071/evidences/post/` -- screenshots taken during verification

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
3. Screenshots go under `ai-dev/active/CR-00071/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB
via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`). It reflects
current production state. It does **not** contain data that only exists in
`scripts/e2e_seed.py`'s baseline unless that script has been explicitly run.

If your verifications require data not yet in production (e.g. a new document
type, diagram rows, or specific work-item history), add a fixture file:

```
ai-dev/active/CR-00071/e2e_fixtures/001_<descriptive_name>.py
```

The file must export `def seed(db: Session) -> None`. Make it idempotent
(`db.get(...)` before insert). Multiple files load in lexical order; use
`001_`, `002_`, … prefixes.

**Module diagram fixtures:** if you seed a `diagram-module-X` doc, the `X`
must match the module's URL slug as produced by the parser:
`path.strip("/").replace("/", "-").lower()` — e.g. `orch/rag/` → `orch-rag`,
so the doc_id must be `diagram-module-orch-rag`. The module must also appear
in the architecture-map doc (`diagram-architecture`) or the base seed's
`LEVEL1_CONTENT` so it shows up in the UI's module list.

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

This CR extends the AI Assistant context-usage percentage indicator (CR-00067)
to **Pi runtime** chat tabs. The percentage is the small value shown to the left
of the **Clear** button in the AI Assistant message-box footer. The AI Assistant
opens from the left edge of any project page (an "AI Assistant" panel with an
"Expand AI Assistant panel" button). A chat tab carries a small model badge; Pi
tabs use a `pi/...` model.

Note on graceful degradation: the percentage is **only** shown when the chat has
real token usage AND the model has a known context window. A brand-new empty Pi
tab correctly shows **no** percentage — that is expected behaviour, not a defect.

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

> This verification is automatically prepended by the qv-browser agent before any work-item-specific V steps. Work item authors do NOT need to write V0 — it runs unconditionally. It is documented here so design reviewers understand what the agent will check.

The agent will visit every distinct page route referenced in V1..V(n) and:

- Extract all fragment references (`hx-target="#X"`, `hx-include="#X"`, `aria-controls="X"`, `aria-labelledby="X"`, `href="#X"`, `for="X"`) from the rendered HTML via `curl`.
- Verify each referenced `id="X"` is present in the same HTML response.
- Read `.playwright-cli/console-*.log` after each page load to detect unhandled JS or HTMX errors.
- Flag any dangling reference or unhandled load-time error as a V0 FAIL.

**If V0 fails, V1..V(n) still run** — V0 failure does not skip the remaining verifications. The `overall_status` is `fail` and the V0 finding appears first in the `--reason`.

### V1: AI Assistant footer renders on a Pi tab; no-data graceful degradation (AC2)

1. Navigate to `$IW_BROWSER_BASE_URL` and open a project page (e.g. the `iw-ai-core` project home).
2. Click the "Expand AI Assistant panel" button on the left edge to open the AI Assistant. The default tab uses the Pi runtime (its model badge is a `pi/...` model) — this is the runtime under test.
3. **Verify:** the message-box footer renders correctly — the Clear, Abort, and Send buttons are present and laid out in one row. The context-percentage element (`#chat-assistant-context-pct`) exists in the DOM immediately to the left of the Clear button. On a fresh Pi tab with no token usage yet, this element is **hidden / shows no text** — confirm it does NOT show `0%` or any placeholder. Confirm no load-time JS console errors.
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/CR-00071/evidences/post/CR-00071_v1_pi_footer_nodata.png`.

### V2: Percentage appears for a Pi tab after a real conversation (AC1, AC5)

1. In the AI Assistant Pi tab, type a short prompt into the input box (e.g. "Say hello in one sentence.") and send it. This drives a real Pi conversation so the assistant message accrues token usage — the rationale is that `context_pct` is computed from actual message token counts.
2. Wait for the assistant's reply to finish streaming.
3. **Verify:** after the reply completes, a numeric percentage (e.g. `2%`) appears to the **left of the Clear button**. Switching away to another tab and back, or waiting for the ~5 s poll, keeps the value present and current. If usage crosses the CR-00067 colour thresholds the tone changes (neutral below 70%, amber 70–89%, red 90%+) — for a short chat the neutral tone is expected. Confirm no console errors.
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/CR-00071/evidences/post/CR-00071_v2_pi_pct_visible.png`.

> If a live Pi conversation cannot be completed in the E2E stack — e.g. the `pi`
> binary is unavailable in the app container, or the runtime returns 503 — this
> is an environment gap, **not** a code defect. Classify it `ENV_DATA_MISSING`,
> capture the evidence, and explain in the report (see Pass Criteria). Do NOT
> mark it a code defect and do NOT trigger a fix cycle for it.

### V3: No Regressions

1. Revisit the AI Assistant footer controls: confirm Clear, Abort, and Send still work (Clear resets the tab, Send/Abort toggle correctly during a run), the tab strip and model badge render normally, and switching tabs behaves as before.
2. Open an OpenCode tab if one is available (create a new tab and pick an OpenCode model) and confirm its context percentage still behaves as it did under CR-00067 — the OpenCode path must be unaffected.
3. Verify no new console errors appeared on any page visited during V1..V2.
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/CR-00071/evidences/post/CR-00071_v3_no_regressions.png`.

## Pass Criteria

All V1..V(n) must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

### Distinguishing code defects from environment gaps and spec mismatches

Before failing the step, classify the failure using one of three classes:

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw console exception | CODE_DEFECT | normal `--reason` |
| Page rendered cleanly but element/data missing because seed lacks it | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` + add fixture |
| Page rendered cleanly, element correctly absent per design doc, V step asks for it anyway | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V{N} ..."` |
| Page rendered cleanly, design says element should be present, it isn't | CODE_DEFECT | normal `--reason` |

- **CODE_DEFECT** -- the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI that the design says should be present. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** -- the page rendered cleanly with HTTP 200 but showed an empty-state message ("No items yet", "No retries — clean run", "0 results") because the E2E DB lacks the historical rows the verification expects, or a live Pi run could not be performed. The fix-cycle agent **cannot** fix this by editing code. Prefix the reason with `ENV_DATA_MISSING:` so the daemon recognises the class:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V2 requires a live Pi conversation but the pi binary is unavailable in the app container — cannot drive token usage end-to-end" \
    --report ai-dev/active/CR-00071/reports/CR-00071_S08_BrowserVerification_Report.md
  ```

  The reason is for the human reviewer; the fix path is environment provisioning, not a code retry.

- **SPEC_MISMATCH** -- the page rendered cleanly, the element is correctly absent according to the design document, but the V step asks the agent to assert the element is present. The verification spec is wrong; the implementation is correct. Prefix with `SPEC_MISMATCH:` and cite the design doc location:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "SPEC_MISMATCH: V{N} expects ... but design doc at ai-dev/active/CR-00071/CR-00071_CR_Design.md §... says ... — verification spec is wrong, not the implementation." \
    --report ai-dev/active/CR-00071/reports/CR-00071_S08_BrowserVerification_Report.md
  ```

  The fix-cycle agent MUST NOT attempt code patches for SPEC_MISMATCH findings. The verification step itself needs to be corrected.

### No cascading `n/a` — seed on demand

Work item authors MUST NOT write "blocked by V2 — n/a" chains in verification specs. The agent is responsible for creating missing preconditions itself. The accepted methods (in order) are:

1. Use a CLI command or dashboard route that the implementation provides.
2. Add or extend `ai-dev/active/CR-00071/e2e_fixtures/NNN_<name>.py` and re-run the seed inside the app container.
3. Write the row directly via the per-worktree DB if the design supplies the SQL.

Only document a V as potentially `n/a` when it can only be satisfied by code that is itself known to be broken in an upstream dependency — and even then the agent will attempt methods (1)..(3) first. A run with one `fail` and four `n/a` is a workflow defect, not a valid report.

## Report

After verification, write `ai-dev/active/CR-00071/reports/CR-00071_S08_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V(n).
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V3.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00071/reports/CR-00071_S08_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00071/reports/CR-00071_S08_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "qv-browser",
  "work_item": "CR-00071",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Pi footer renders; no-data graceful degradation", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Percentage appears for a Pi tab after a real conversation", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed or was legitimately `n/a`. `fail` on any failure.
- `overall_failure_class`: the most severe failure class observed across all Vs. Severity order for human routing: `spec_mismatch` > `env_data_missing` > `code_defect`. Set to `null` when `overall_status` is `pass`.
- `failure_class` per verification: set to `null` when status is `pass` or `n/a`.
- `base_url_used`: The concrete URL the agent actually hit -- used by reviewers to confirm the worktree stack (not the dev server) was tested.
- `console_errors_observed`: Any console errors seen during any V(n), even if the verification otherwise passed. A non-empty list on a passing run should be flagged in the report.
