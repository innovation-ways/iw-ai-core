# Browser Verification Prompt: F-00087-S13-BrowserVerification

**Work Item**: F-00087 -- Pi runtime + per-tab runtime selection in AI Assistant chat
**Step**: S13
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
infrastructure containers are outside your scope.

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

`docker compose exec app` is allowed and required when re-running the seed
after writing a fixture file.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against any DB from your step.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports or routes. The port is allocated per-worktree.

Do NOT run any of the following — they will break the isolated stack:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command — the stack is already up
- `playwright install` or `npx playwright install` — the CLI is pre-installed
- `agent-browser` — use `playwright-cli` exclusively
- Any `chromium.launch()` Python/Node snippet

## Input Files

- `ai-dev/active/F-00087/F-00087_Feature_Design.md` — the design document
- All files modified by S01/S04/S05 (recorded in their respective `_report.md` files)

## Output Files

- `ai-dev/active/F-00087/reports/F-00087_S13_BrowserVerification_Report.md` — the mandatory report
- `ai-dev/active/F-00087/evidences/pre/` — pre-state screenshot (F-00086 baseline — captured here at execution time since F-00087's modal is the F-00086 modal with Pi added)
- `ai-dev/active/F-00087/evidences/post/` — post-implementation screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in if needed:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:

1. Always call `playwright-cli snapshot` before `fill`/`click` to read current refs.
2. Wait for transitions before snapshotting again.
3. Screenshots go under `ai-dev/active/F-00087/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's Postgres is seeded from production via `pg_dump`. CR-00062's `agent_runtime_options` Pi rows are present (the seed includes those rows since CR-00062 is merged).

The `pi` binary needs to be available in the E2E stack. If the stack ships with `pi` pre-installed, V2..V5 will exercise the real runtime. If `pi` is missing, V2's create-tab POST will return 503 — that is a **stack-config issue (ENV_DATA_MISSING)**, not a code defect; report with `--reason "ENV_DATA_MISSING: ..."` and document the gap for the operator.

If verifications require fixture data (e.g., a specific opencode.json permission policy for V4), add an idempotent fixture under `ai-dev/active/F-00087/e2e_fixtures/001_<name>.py` and re-run the seed inside the app container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠ Never run `uv run python scripts/e2e_seed.py` from the host shell.

## Verification Steps

### V0: Pre-flight page sanity (built-in)

Automatically prepended.

### V1: Pre-state evidence + runtime dropdown shows BOTH OpenCode and Pi

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/`.
2. Expand the AI Assistant panel.
3. Click "+" to open the create-tab modal.
4. **Pre-state screenshot**: capture the BASELINE state of the modal as F-00086 ships it — the runtime dropdown WITH Pi (since F-00087 has been merged). Save to `ai-dev/active/F-00087/evidences/pre/F-00087-create-tab-modal-with-pi.png` so reviewers can see the dropdown.
5. Click the "Runtime" dropdown.
6. **Verify:** Exactly TWO options appear — "OpenCode" (default) and "Pi".
7. **Screenshot:** `ai-dev/active/F-00087/evidences/post/F-00087_v1_runtime_dropdown_two_options.png`.

### V2: Selecting Pi populates the model dropdown with Pi models

1. With the modal still open, select "Pi" in the runtime dropdown.
2. **Verify:** The model dropdown re-fetches and populates with Pi models (look for `pi/minimax/MiniMax-M2.7` or `pi/openai/gpt-5.3-codex` per CR-00062's seeded rows).
3. **Verify:** No OpenCode-only models (e.g., `anthropic/claude-sonnet-4-7`) appear in the list while Runtime=Pi.
4. Switch back to "OpenCode" — verify model list re-fetches with OpenCode models.
5. **Screenshot:** `ai-dev/active/F-00087/evidences/post/F-00087_v2_model_list_per_runtime.png`.

### V3: Create 1 OpenCode + 2 Pi tabs with different models

1. Create Tab O: runtime=OpenCode, model=`anthropic/claude-sonnet-4-7` (or whatever's available), title="Tab O".
2. Create Tab P1: runtime=Pi, model=`pi/minimax/MiniMax-M2.7`, title="Tab P1".
3. Create Tab P2: runtime=Pi, model=`pi/openai/gpt-5.3-codex`, title="Tab P2".
4. **Verify:** All three tabs visible in the strip. Each tab's per-tab model badge above the composer shows its own model when activated.
5. Click each tab and verify its per-tab model dropdown lists ONLY its runtime's models (Tab P1 cannot switch to an OpenCode model; Tab O cannot switch to a Pi model).
6. **Screenshot:** `ai-dev/active/F-00087/evidences/post/F-00087_v3_mixed_tabs_created.png`.

### V4: Send prompts in all three tabs; verify independent streaming

1. In Tab O, send "hello from opencode".
2. In Tab P1, send "hello from pi-1".
3. In Tab P2, send "hello from pi-2".
4. **Verify:** Each tab streams its own response. Switching between tabs shows their independent transcripts.
5. **Verify:** No cross-pollination — Tab O's transcript contains only opencode response; P1 contains only pi-1; P2 only pi-2.
6. **Screenshot:** `ai-dev/active/F-00087/evidences/post/F-00087_v4_three_independent_streams.png`.

### V5: Abort one Pi tab; others continue

1. In Tab P1, send a longer prompt ("write a haiku and explain each line in detail").
2. While Tab P1 is streaming, switch to Tab P2 and send "say hi".
3. Switch to Tab P1 and click its Abort button.
4. **Verify:** Tab P1's stream stops with an aborted marker.
5. Switch to Tab O and Tab P2.
6. **Verify:** Both Tab O and Tab P2 streams completed normally; Tab P1's abort did NOT cascade.
7. **Screenshot:** `ai-dev/active/F-00087/evidences/post/F-00087_v5_pi_abort_isolation.png`.

### V6: Approval modal works on a Pi tab

**Pre-req:** the project's `.opencode/opencode.json` must have at least one `permission.bash[<pattern>] = "ask"` entry. The iw-ai-core production config has everything as "allow"; for this verification, write a fixture that overrides it for the test stack (`ai-dev/active/F-00087/e2e_fixtures/001_ask_policy.py` writes `.opencode/opencode.json` with `permission.bash["rm *"] = "ask"`). Re-run the seed inside the app container as documented above.

1. In Tab P1, send a prompt that the agent will likely respond to by invoking `bash` with `rm <something>`. (For deterministic testing, the stub `pi` may need to be replaced by a "real-ish" subprocess; if the test stack uses the stub, V6 may not surface a real `tool_call`. Document in the report if this V cannot be exercised in the current stack and mark as `n/a` with reason `ENV_DATA_MISSING: stack does not run real pi binary; approval flow exercised by S05 integration tests instead`.)
2. If a real `pi` runs: verify the approval modal appears with the tool name "bash" and the args showing the `rm <X>` command.
3. Click Approve. Verify the modal closes and the tool executes (the Pi agent's response continues).
4. **Screenshot:** `ai-dev/active/F-00087/evidences/post/F-00087_v6_pi_approval_modal.png` (or empty-state screenshot if marked `n/a`).

### V7: Reload page, all tabs persist

1. Refresh the browser (`playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/"`).
2. Re-expand the AI Assistant panel.
3. **Verify:** Tab O, Tab P1, Tab P2 all reappear in the strip.
4. Click each tab and verify its transcript is restored.
5. **Verify:** Clicking a Pi tab whose subprocess was killed (dashboard restart drops all Pi subprocesses) does not show an error; the next prompt spawns a fresh subprocess and resumes.
6. Send a follow-up prompt in Tab P1 and verify the response references prior conversation context (proves `pi --session <path>` resumed history).
7. **Screenshot:** `ai-dev/active/F-00087/evidences/post/F-00087_v7_tabs_persist_pi_respawn.png`.

### V8: No Regressions

1. Re-visit adjacent flows:
   - Dashboard home renders without 5xx and without console errors.
   - The toggle-AI-Assistant-panel button (Ctrl+/) still works.
   - F-00086's "Recent closed tabs" menu still works for OpenCode tabs.
2. **Verify:** No new console errors appeared during V1..V7.
3. **Screenshot:** `ai-dev/active/F-00087/evidences/post/F-00087_v8_no_regressions.png`.

## Pass Criteria

All V1..V8 must pass. V6 may be `n/a` with `ENV_DATA_MISSING:` if the stack does not run a real Pi binary; document the gap. Any other failure requires `iw step-fail` with a classified reason (CODE_DEFECT / ENV_DATA_MISSING / SPEC_MISMATCH).

## Report

After verification, write `ai-dev/active/F-00087/reports/F-00087_S13_BrowserVerification_Report.md` containing:

- Pass/fail table with one row per V1..V8.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with file:line references if root-caused.
- List of captured screenshots (relative paths under `evidences/`).
- A "No regressions observed" subsection covering V8.

Then call one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00087/reports/F-00087_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason with classification prefix if applicable>" \
  --report ai-dev/active/F-00087/reports/F-00087_S13_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "F-00087",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Runtime dropdown shows OpenCode + Pi", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Model list per runtime", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Mixed tabs created", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Three independent streams", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Pi abort isolation", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Pi approval modal", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V7", "name": "Reload persistence + pi respawn", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V8", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
