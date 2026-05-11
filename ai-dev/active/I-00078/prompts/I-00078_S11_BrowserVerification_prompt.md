# Browser Verification Prompt: I-00078-S11-BrowserVerification

**Work Item**: I-00078 -- Dashboard layout: invisible dark-mode scrollbars, double vertical scrollbar hiding the footer, and a full-width footer with the theme toggle inside it
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

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:3100`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment (often the dev server serving `main` branch instead of your feature worktree).

Do NOT hardcode application **route paths** either (e.g. `/project/{id}/work/{item}` vs `/project/{id}/item/{item}`). Routes drift; a stale path in a verification prompt fails with a 404 that *looks* like a code defect but is a spec mismatch. Prefer to **navigate via the UI** — open a list/index page (`/history`, `/batches`, the project home) and click the link/row for the entity under test, exactly as a user would. The detail-page URL the app actually uses is whatever that link resolves to. Only fall back to a direct URL when no UI path exists, and when you do, treat any 404 as "the prompt's URL is wrong" (`spec_mismatch`), not a code defect — and report the corrected path.

Before asserting on the *content* of any page, first confirm the page itself **loaded successfully** (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors). A 500 on the page that contains the element you're verifying is itself a `code_defect` finding — capture the server traceback (it's usually in the response body or the app container logs) and report it; do not retry the same navigation expecting a different result.

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00078/I-00078_Issue_Design.md` -- the design document
- `dashboard/templates/base.html` -- the restructured app shell + full-width footer + relocated theme toggle
- `dashboard/static/theme.css` -- dark-mode scrollbar colours (`--scrollbar-thumb` / `:hover` / Firefox `scrollbar-color`)
- `dashboard/static/styles.css` -- `.iw-pipeline-strip` bottom padding (+ any appended plain CSS for the dvh shell)
- `dashboard/templates/fragments/llm_usage_footer.html` -- the htmx-swapped meters body inside the footer
- `dashboard/templates/components/step_pipeline.html` -- the step-pipeline strip macro
- `ai-dev/active/I-00078/evidences/pre/I-00078-dark-mode-item-page.png` -- pre-fix reference screenshot

## Output Files

- `ai-dev/active/I-00078/reports/I-00078_S11_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/I-00078/evidences/post/` -- screenshots taken during verification

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

(If the E2E stack has no login screen — it may go straight to the dashboard — skip the login step and proceed.)

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00078/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB
via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`). It reflects
current production state. It does **not** contain data that only exists in
`scripts/e2e_seed.py`'s baseline unless that script has been explicitly run.

If your verifications require data not yet in production (e.g. a new document
type, diagram rows, or specific work-item history), add a fixture file:

```
ai-dev/active/I-00078/e2e_fixtures/001_<descriptive_name>.py
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

> Note for this item: the verifications below need (a) any page that extends `base.html` — the project home and `/system/status` always work — and (b) some page whose **step pipeline overflows horizontally** so the pipeline scrollbar shows. The production-seeded DB normally has work items with 14–16 steps (e.g. an `I-000xx` with fix-cycle rerun pills) whose strip overflows in a normal-width browser; navigate to the History list and open the item with the most steps. If no item's pipeline overflows even after narrowing the browser width, treat V2 as ENV_DATA_MISSING and add an `e2e_fixtures` file that seeds a work item with ~16 step rows including a couple of fix-cycle reruns — do not skip V2.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

> This verification is automatically prepended by the qv-browser agent before any work-item-specific V steps. Work item authors do NOT need to write V0 — it runs unconditionally. It is documented here so design reviewers understand what the agent will check.

The agent will visit every distinct page route referenced in V1..V(n) and:

- Extract all fragment references (`hx-target="#X"`, `hx-include="#X"`, `aria-controls="X"`, `aria-labelledby="X"`, `href="#X"`, `for="X"`) from the rendered HTML via `curl`.
- Verify each referenced `id="X"` is present in the same HTML response.
- Read `.playwright-cli/console-*.log` after each page load to detect unhandled JS or HTMX errors.
- Flag any dangling reference or unhandled load-time error as a V0 FAIL.

**If V0 fails, V1..V(n) still run** — V0 failure does not skip the remaining verifications. The `overall_status` is `fail` and the V0 finding appears first in the `--reason`.

### V1: Full-width footer is always visible and contains the theme toggle (AC3, AC4)

1. Navigate to `{{IW_BROWSER_BASE_URL}}/` (the project list / home — any page that extends `base.html`).
2. Without scrolling, look at the bottom of the viewport. The footer bar (left: a "☾ Theme" / "Toggle theme" button; then the Claude meter, the MiniMax meter, and "IW AI Core v0.1" pinned to the far right) must be **fully visible** at the bottom edge of the window — not cut off, not requiring a scroll. The footer must extend the **full width of the window**, including the strip directly below the left navigation sidebar (i.e. the footer's left edge is at the window's left edge, not at the sidebar's right edge).
3. **Verify:** the footer is visible at the bottom without scrolling; its left edge aligns with the window's left edge (it spans under the sidebar); it contains a control with accessible text "Toggle theme" (or labelled "Toggle theme"); the left navigation sidebar no longer contains a "Toggle theme" control. Confirm there are **no** load-time console errors.
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00078/evidences/post/I-00078_v1_full_width_footer.png`.

### V2: Step-pipeline horizontal scrollbar is separated from the pills (AC2)

1. From `{{IW_BROWSER_BASE_URL}}/`, navigate the UI to the project's History list and open the work item with the most pipeline steps (an item with ~14–16 steps whose pipeline strip overflows horizontally — e.g. one with fix-cycle rerun pills). If needed, also narrow the browser window so the strip definitely overflows.
2. Scroll to the "STEP PIPELINE" strip on the Overview tab. There must be a horizontal scrollbar under the row of step pills, with **visible vertical spacing** between the bottom edge of the pills and the scrollbar (the scrollbar is not flush against the pills).
3. **Verify:** the pipeline strip shows a horizontal scrollbar with clear spacing below the pills; scrolling the strip horizontally works and reveals the off-screen pills. No console errors.
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00078/evidences/post/I-00078_v2_pipeline_scrollbar_spacing.png`.

### V3: Dark-mode scrollbars are clearly visible; theme toggle still works (AC1, AC4)

1. On a page with a long body (the item Overview page from V2, or `{{IW_BROWSER_BASE_URL}}/system/status`), click the **"Toggle theme"** button **in the footer** to switch to dark mode (if the stack already starts in dark mode, click it to go light, screenshot, then click again to return to dark).
2. With the page in **dark** mode and the content tall enough to overflow, observe the right-hand vertical scrollbar of the page content area and (if present) the horizontal scrollbar of the pipeline strip. The scrollbar thumb must be **clearly visible** against the dark background — not the near-invisible dark-on-dark it was before. Hover the pointer over the vertical scrollbar thumb and confirm it visibly changes shade (hover state).
3. **Verify:** clicking the footer's "Toggle theme" flips the whole UI between light and dark and the choice persists across a page reload (`localStorage`); in dark mode the scrollbar thumb is plainly visible and has a hover state. No console errors.
4. **Screenshot (dark, scrollbar visible):** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00078/evidences/post/I-00078_v3_dark_scrollbar_visible.png`.

### V4: Exactly one vertical scrollbar; layout fills the viewport (AC3)

1. On a tall page (the item Overview page, or `{{IW_BROWSER_BASE_URL}}/system/status` if long enough), at a normal browser window size, inspect the right edge of the window.
2. There must be **exactly one** vertical scrollbar — the page content scroller inside `<main>`. There must NOT be a second scrollbar belonging to the whole page/body. The header (global search bar) stays pinned at the top, the footer stays pinned at the bottom, and only the middle content area scrolls.
3. **Verify:** one vertical scrollbar only; scrolling moves the content area while the header and footer stay fixed; the footer remains visible at the bottom throughout. (If a "schema is behind head" banner happens to be shown at the top, the layout still fits the screen and the footer is still visible — note this if observed.)
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00078/evidences/post/I-00078_v4_single_scrollbar.png`.

### V5: No Regressions

1. Revisit adjacent chrome behaviour: the global search bar still works (type a query, results appear); the left sidebar's "Projects" / "System" sections still expand/collapse; navigating between a couple of pages (project Dashboard, History, a `/system/*` page) renders cleanly with the header pinned top and footer pinned bottom on each; the htmx footer poll (or a manual reload) does **not** make the "Toggle theme" button disappear; on a narrow window the mobile hamburger still opens/closes the sidebar over a backdrop.
2. Verify no new console errors appeared on any page visited during V1..V4.
3. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00078/evidences/post/I-00078_v5_no_regressions.png`.

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
- **ENV_DATA_MISSING** -- the page rendered cleanly with HTTP 200 but showed an empty-state message ("No items yet", "No retries — clean run", "0 results") because the E2E DB lacks the historical rows the verification expects. The fix-cycle agent **cannot** fix this by editing code; it needs an `e2e_fixtures` file. Prefix the reason with `ENV_DATA_MISSING:` so the daemon recognises the class:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V2 needs a work item whose step pipeline overflows (~16 steps + fix-cycle reruns) — add ai-dev/active/I-00078/e2e_fixtures/001_long_pipeline_item.py" \
    --report ai-dev/active/I-00078/reports/I-00078_S11_BrowserVerification_Report.md
  ```

  The reason is for the human reviewer; the fix path is to add a fixture, not to retry.

- **SPEC_MISMATCH** -- the page rendered cleanly, the element is correctly absent according to the design document, but the V step asks the agent to assert the element is present. The verification spec is wrong; the implementation is correct. Prefix with `SPEC_MISMATCH:` and cite the design doc location:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "SPEC_MISMATCH: V4 expects ... but design doc at ai-dev/active/I-00078/I-00078_Issue_Design.md:§... says ... — verification spec is wrong, not the implementation." \
    --report ai-dev/active/I-00078/reports/I-00078_S11_BrowserVerification_Report.md
  ```

  The fix-cycle agent MUST NOT attempt code patches for SPEC_MISMATCH findings. The verification step itself needs to be corrected.

### No cascading `n/a` — seed on demand

Work item authors MUST NOT write "blocked by V2 — n/a" chains in verification specs. The agent is responsible for creating missing preconditions itself. The accepted methods (in order) are:

1. Use a CLI command or dashboard route that the implementation provides (e.g., `iw batch-create --no-auto-merge`).
2. Add or extend `ai-dev/active/I-00078/e2e_fixtures/NNN_<name>.py` and re-run the seed inside the app container.
3. Write the row directly via the per-worktree DB if the design supplies the SQL.

Only document a V as potentially `n/a` when it can only be satisfied by code that is itself known to be broken in an upstream dependency — and even then the agent will attempt methods (1)..(3) first. A run with one `fail` and four `n/a` is a workflow defect, not a valid report.

## Report

After verification, write `ai-dev/active/I-00078/reports/I-00078_S11_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V(n).
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V(n).

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00078/reports/I-00078_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00078/reports/I-00078_S11_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00078",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Full-width footer visible + theme toggle inside", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Pipeline scrollbar separated from pills", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Dark-mode scrollbars visible + theme toggle works", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Exactly one vertical scrollbar; layout fills viewport", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""}
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
