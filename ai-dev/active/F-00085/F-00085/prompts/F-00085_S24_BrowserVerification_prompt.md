# Browser Verification Prompt: F-00085-S24-BrowserVerification

**Work Item**: F-00085 -- Auto-Merge Resolver — Observability + Per-Project Control
**Step**: S24
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

- `ai-dev/active/F-00085/F-00085_Feature_Design.md` -- the design document (ACs 1..14)
- `ai-dev/active/F-00085/F-00085_Functional.md` -- the functional doc
- Pre-state evidence (header before chip, route 404 before page existed):
  - `ai-dev/active/F-00085/evidences/pre/F-00085_pre_dashboard_no_chip.png`
  - `ai-dev/active/F-00085/evidences/pre/F-00085_pre_route_404.png`
- Implementation files (from prior steps; for context only — do not modify):
  - `dashboard/routers/auto_merge_ui.py`
  - `dashboard/templates/pages/project/auto_merge.html`
  - `dashboard/templates/fragments/auto_merge_status_chip.html`
  - `dashboard/templates/fragments/auto_merge_events_table.html`
  - `dashboard/templates/fragments/auto_merge_event_detail.html`
  - `dashboard/templates/fragments/auto_merge_rollup.html`
  - `dashboard/templates/fragments/auto_merge_refuse_list.html`
  - `dashboard/templates/fragments/auto_merge_settings.html`
  - `dashboard/templates/base.html`
  - `dashboard/static/styles.css`

## Output Files

- `ai-dev/active/F-00085/reports/F-00085_S24_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/F-00085/evidences/post/` -- screenshots taken during verification

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

Replace the V1..V(n) below with concrete, per-acceptance-criterion verifications derived from the feature design. Each verification must state:

1. **What to navigate to** -- a route under `{{IW_BROWSER_BASE_URL}}` (the platform substitutes this placeholder with the concrete base URL at launch time, so the LLM sees a real URL).
2. **What to click or type** -- with a one-sentence rationale explaining why that interaction triggers the feature.
3. **What to verify** -- exact text, element visibility, URL change, or the absence of console errors.
4. **Capture an evidence screenshot:** `playwright-cli screenshot` (no path argument — saves to `.playwright-cli/page-<ts>.png`), then `cp .playwright-cli/page-*.png ai-dev/active/{{ID}}/evidences/post/{{ID}}_v{N}_{{short_name}}.png`. Passing a path to `playwright-cli screenshot` is invalid — the tool treats it as a page element ref and errors.

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

> This verification is automatically prepended by the qv-browser agent before any work-item-specific V steps. Work item authors do NOT need to write V0 — it runs unconditionally. It is documented here so design reviewers understand what the agent will check.

The agent will visit every distinct page route referenced in V1..V(n) and:

- Extract all fragment references (`hx-target="#X"`, `hx-include="#X"`, `aria-controls="X"`, `aria-labelledby="X"`, `href="#X"`, `for="X"`) from the rendered HTML via `curl`.
- Verify each referenced `id="X"` is present in the same HTML response.
- Read `.playwright-cli/console-*.log` after each page load to detect unhandled JS or HTMX errors.
- Flag any dangling reference or unhandled load-time error as a V0 FAIL.

**If V0 fails, V1..V(n) still run** — V0 failure does not skip the remaining verifications. The `overall_status` is `fail` and the V0 finding appears first in the `--reason`.

### V1: Header chip is HIDDEN when resolved phase = 0 (AC6, Invariant 6)

**Precondition seed**: ensure `auto_merge_project_config` has NO row for the project under test, AND the TOML `phase = 0` is the resolved value. The E2E stack's seed reflects production; check `executor/auto_merge.toml` inside the worktree. If TOML says `phase = 1`, write a fixture under `ai-dev/active/F-00085/e2e_fixtures/001_phase0_for_test_project.py` that inserts an `auto_merge_project_config` row with `phase = 0` for a known project id. Re-run the seed via `docker compose exec` per Prerequisites.

1. Navigate to the project's Queue page (use the sidebar nav from the project home — do NOT hardcode the route path).
2. `playwright-cli snapshot` and inspect the rendered HTML.
3. **Verify:** the status chip DOM element is **absent** from the header — not just visually hidden via CSS, but missing entirely (the template's `{% if %}` is gating the include). Confirm by curl-fetching the page HTML and asserting the auto-merge status-chip element does not appear.
4. **Verify:** no console errors on the page load.
5. **Screenshot:** save to `ai-dev/active/F-00085/evidences/post/F-00085_v1_phase0_no_chip.png`.

### V2: Header chip is VISIBLE when resolved phase >= 1 (AC2, AC11)

**Precondition seed**: insert `auto_merge_project_config` row with `phase = 1`, `runtime_option_id = 4` (claude/claude-sonnet-4-6) for the test project — write a fixture `ai-dev/active/F-00085/e2e_fixtures/002_phase1_with_runtime.py` and re-seed.

1. Navigate to the project's Queue page (same as V1).
2. `playwright-cli snapshot`.
3. **Verify:** the status chip is now visible in the header.
4. **Verify:** the chip's text content includes the phase label (e.g., "PHASE 1") and the resolved runtime ("claude/claude-sonnet-4-6") and the "per-project override" annotation.
5. **Verify:** the chip's health indicator renders (any of green/yellow/red/grey is acceptable here; V5 specifically checks the green-on-success transition).
6. **Screenshot:** `ai-dev/active/F-00085/evidences/post/F-00085_v2_phase1_chip_visible.png`.

### V3: Auto-Merge page renders empty state for the test project (AC1)

**Precondition**: ensure no `merge_auto_*` events exist for the test project (the fresh fixture should have none).

1. Click the **Auto-Merge** sidebar nav row.
2. `playwright-cli snapshot`.
3. **Verify:** the page URL ends in `/auto-merge`.
4. **Verify:** the page shows the rich status chip card (phase, runtime, deployed_since timestamp).
5. **Verify:** the events table shows the empty-state message "No auto-merge events yet — Phase 1 only fires on merge-queue conflicts in tests/**, docs/**, ai-dev/active/**/reports/**" (verbatim per AC1).
6. **Verify:** the refuse-list widget is **not rendered** (hidden when zero events per AC7).
7. **Verify:** the verdict rollup widget shows "0 events" for both 7d and 30d windows.
8. **Verify:** the token-cost rollup shows "$0.00".
9. **Verify:** the Settings panel is rendered with phase dropdown set to `1` and the runtime picker showing `claude / claude-sonnet-4-6`.
10. **Screenshot:** `ai-dev/active/F-00085/evidences/post/F-00085_v3_empty_state_page.png`.

### V4: Auto-Merge page renders seeded events with inline verdict widgets (AC2)

**Precondition seed**: write a fixture `ai-dev/active/F-00085/e2e_fixtures/003_seeded_events.py` that inserts 3 `merge_auto_resolution_attempted` + 3 `merge_auto_resolved` events for the test project. Each `merge_auto_resolved` event metadata MUST include a realistic `llm_calls` array (file_path, proposed_content, model, input_tokens, output_tokens). Re-seed.

1. Reload `/auto-merge`.
2. `playwright-cli snapshot`.
3. **Verify:** the events table now shows 6 rows.
4. **Verify:** each `merge_auto_resolved` row displays the inline verdict widget with `[pending] [correct] [wrong] [partial]` buttons; `[pending]` is highlighted.
5. **Verify:** `merge_auto_resolution_attempted` rows show NO verdict widget.
6. **Screenshot:** `ai-dev/active/F-00085/evidences/post/F-00085_v4_seeded_events_with_inline_verdicts.png`.

### V5: Inline verdict click persists to the DB (AC3)

1. From V4 state, click the `[correct]` button on the first `merge_auto_resolved` row.
2. Wait for htmx swap to complete.
3. `playwright-cli snapshot`.
4. **Verify:** the row re-renders with `[correct]` highlighted instead of `[pending]`.
5. **Verify:** the verdict rollup widget now shows `correct=1` in the 7d window (htmx hx-trigger should refresh it; if not, scroll to it and verify).
6. **Reload the page entirely** to confirm persistence.
7. **Verify after reload:** the row still shows `[correct]` highlighted.
8. **Screenshot:** `ai-dev/active/F-00085/evidences/post/F-00085_v5_inline_verdict_persisted.png`.

### V6: Modal diff viewer shows proposed vs current main (AC4)

1. Click the `(view)` link or click the row body of a `merge_auto_resolved` event.
2. Wait for the modal to open.
3. `playwright-cli snapshot`.
4. **Verify:** the modal title contains the event id or timestamp.
5. **Verify:** the left pane label reads "Proposed by LLM"; the right pane label reads "Currently on main" (or "(file no longer exists on main)" if the fixture's `file_path` was set to a known-missing path).
6. **Verify:** the left pane contains the `proposed_content` from the seeded event metadata.
7. **Verify:** the right pane has content (or the placeholder).
8. **Verify:** the modal also shows a verdict widget with the same 4 buttons + a notes textarea + a Save button.
9. **Screenshot:** `ai-dev/active/F-00085/evidences/post/F-00085_v6_modal_diff_viewer.png`.

### V7: Modal verdict + notes both persist (AC3, AC4)

1. From V6 state, change the verdict to `[partial]` and type "ambiguous — kept LLM proposal but tweaked one line manually" into the notes textarea.
2. Click Save.
3. Wait for htmx swap.
4. Close the modal.
5. Open the same event modal again.
6. **Verify:** the verdict widget shows `[partial]` highlighted AND the notes textarea is populated with the saved text.
7. **Screenshot:** `ai-dev/active/F-00085/evidences/post/F-00085_v7_modal_verdict_and_notes_persist.png`.

### V8: Settings panel writes phase + runtime (AC12)

1. From the Auto-Merge page, scroll to the Settings panel.
2. Change the phase dropdown from `1` to `0`.
3. Click Save.
4. Wait for htmx swap.
5. **Verify:** the status chip on the page header re-renders to show "PHASE 0" (or disappears if your implementation hides it on phase=0).
6. Navigate to the Queue page (sidebar).
7. **Verify:** the compact header chip is NO LONGER rendered on the Queue page (AC6).
8. Navigate back to `/auto-merge`.
9. **Verify:** the page now shows the plumbing-only empty-state message; the Settings panel is still visible.
10. Set phase back to `1`. Click Save.
11. **Verify:** the chip re-appears.
12. **Screenshot:** `ai-dev/active/F-00085/evidences/post/F-00085_v8_settings_phase_toggle.png`.

### V9: Settings runtime picker only shows enabled rows (AC14)

1. Inspect the runtime picker dropdown's options via `playwright-cli snapshot`.
2. **Verify:** the dropdown contains options for `id=1` (opencode/minimax), `id=4` (claude/sonnet), `id=5` (claude/opus), `id=6` (opencode/gpt-5.3-codex) — these are the currently enabled rows.
3. **Verify:** the dropdown does NOT contain options for `id=2` and `id=3` (disabled rows).
4. **Verify:** the dropdown has `<optgroup>`s grouping options by `cli_tool` (claude vs opencode).
5. **Screenshot:** `ai-dev/active/F-00085/evidences/post/F-00085_v9_runtime_picker_no_disabled.png`.

### V10: Refuse-list widget renders when events present (AC7)

**Precondition seed**: write a fixture `ai-dev/active/F-00085/e2e_fixtures/004_refuse_list_events.py` that inserts 3 `merge_auto_resolution_skipped` events with metadata `{"reason": "refuse_list"}` + 1 with `{"reason": "binary"}` + 2 with `{"reason": "phase_0"}`. Re-seed.

1. Reload `/auto-merge`.
2. **Verify:** the refuse-list widget is now visible (was hidden in V3).
3. **Verify:** it shows counts grouped by reason: `refuse_list: 3`, `binary: 1`, `phase_0: 2`.
4. **Screenshot:** `ai-dev/active/F-00085/evidences/post/F-00085_v10_refuse_list_widget.png`.

### V11: Token-cost rollup with per-model breakdown (AC8)

1. From the seeded events in V4 (which include `llm_calls` with `model="claude-sonnet-4-6"`, `input_tokens=10000`, `output_tokens=2000`), the cost is `(10000 * 3 + 2000 * 15) / 1_000_000 = $0.06`.
2. Scroll to the token-cost rollup.
3. **Verify:** the 7d window shows total cost ≈ `$0.18` (3 events × $0.06).
4. **Verify:** the per-model breakdown table shows the model name `claude-sonnet-4-6` with input/output tokens and cost matching the formula.
5. **Screenshot:** `ai-dev/active/F-00085/evidences/post/F-00085_v11_token_cost_rollup.png`.

### V12: No regressions on adjacent project pages (AC9)

1. Visit each of these routes in sequence (use sidebar navigation, NOT hardcoded URLs): Queue, History, Batches, Code, Docs, Research, Tests, Quality, Jobs, Worktrees.
2. For each page:
   - `playwright-cli snapshot` to confirm the page rendered.
   - Check `.playwright-cli/console-*.log` for any new errors compared to the pre-state baseline.
3. **Verify:** every page returns HTTP 200 (no 5xx).
4. **Verify:** no NEW console errors appeared on any page (the existing baseline may have one or two pre-existing errors — those are NOT a regression).
5. **Verify:** the header status chip remains visible on every project page (because phase=1 from V8's restore).
6. **Screenshot:** `ai-dev/active/F-00085/evidences/post/F-00085_v12_no_regressions.png` of the Queue page (representative).

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
    --reason "ENV_DATA_MISSING: V1 expects F-00055 step_runs (S13×3, S10×2) — add ai-dev/active/{{ID}}/e2e_fixtures/001_f00055_history.py" \
    --report ai-dev/active/{{ID}}/reports/{{ID}}_{{STEP}}_BrowserVerification_Report.md
  ```

  The reason is for the human reviewer; the fix path is to add a fixture, not to retry.

- **SPEC_MISMATCH** -- the page rendered cleanly, the element is correctly absent according to the design document, but the V step asks the agent to assert the element is present. The verification spec is wrong; the implementation is correct. Prefix with `SPEC_MISMATCH:` and cite the design doc location:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "SPEC_MISMATCH: V4 expects Plan tab on executing batch but design doc at ai-dev/active/{{ID}}/{{ID}}_Feature_Design.md:§Plan-tab says Plan tab only renders when status in (planning|approved|paused) — verification spec is wrong, not the implementation." \
    --report ai-dev/active/{{ID}}/reports/{{ID}}_{{STEP}}_BrowserVerification_Report.md
  ```

  The fix-cycle agent MUST NOT attempt code patches for SPEC_MISMATCH findings. The verification step itself needs to be corrected.

### No cascading `n/a` — seed on demand

Work item authors MUST NOT write "blocked by V2 — n/a" chains in verification specs. The agent is responsible for creating missing preconditions itself. The accepted methods (in order) are:

1. Use a CLI command or dashboard route that the implementation provides (e.g., `iw batch-create --no-auto-merge`).
2. Add or extend `ai-dev/active/{{ID}}/e2e_fixtures/NNN_<name>.py` and re-run the seed inside the app container.
3. Write the row directly via the per-worktree DB if the design supplies the SQL.

Only document a V as potentially `n/a` when it can only be satisfied by code that is itself known to be broken in an upstream dependency — and even then the agent will attempt methods (1)..(3) first. A run with one `fail` and four `n/a` is a workflow defect, not a valid report.

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
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""}
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
