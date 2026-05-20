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

The `pi` binary does **not** need to be on PATH inside the dashboard container — the dashboard lifespan auto-falls back to the bundled stub at `tests/integration/stubs/pi` when `IW_E2E_SEED=1` is set (which it always is in the E2E compose stack). Running `which pi` inside the container will report "not found", but that is **not** a signal of failure: it just means PATH does not contain the stub directory, while the PiRuntime is configured with the absolute path to the stub.

**Heuristic note for qv-browser**: do NOT use `which pi` or `pi --version` as a litmus test for whether V3..V7 are exercisable. The authoritative signal is whether `POST /api/chat/tabs` with `{"runtime":"pi", ...}` returns 201. If it returns 201, the Pi pipeline is healthy and V3..V7 MUST be attempted. If it returns 503, then either the stub is missing from the image or the dashboard lifespan log will show one of:

- `Pi binary not on PATH; using bundled E2E stub at …` (success path — should not 503)
- `Pi E2E stub at … is not executable; …`
- `IW_E2E_SEED=1 set and `pi` missing on PATH, but the bundled stub at … does not exist; …`

Only when the lifespan logs the latter two should V3..V7 be marked `n/a` with `ENV_DATA_MISSING`. Otherwise treat a 503 as a code defect and report it as such.

V6 specifically — the bundled stub recognises the substring `trigger-approval` in a prompt and emits an `extension_ui_request` with id `iw-chat-approvals.test-001`. Send a prompt containing that exact substring in Tab P1 to exercise the approval modal end-to-end; the policy fixture is not required for that path because the stub bypasses real `.opencode/opencode.json` matching.

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

**Stub-aware testing:** the bundled stub `pi` watches incoming prompts for the substring `trigger-approval`. When it sees that substring, it emits an `extension_ui_request` event with id `iw-chat-approvals.test-001`, tool `bash`, args `{"cmd": "rm temp.txt"}`, and question `"Allow bash to run 'rm temp.txt'?"`. This is sufficient to exercise the approval modal end-to-end without writing a real `.opencode/opencode.json` policy fixture.

1. In Tab P1, send the literal prompt `trigger-approval rm temp.txt`.
2. **Verify:** the F-00086 approval modal appears with tool name "bash" and args containing `cmd: "rm temp.txt"`.
3. Click Approve. **Verify:** the modal closes and Tab P1 receives `tool_execution_end` with `result: "ok"`.
4. **Screenshot:** `ai-dev/active/F-00087/evidences/post/F-00087_v6_pi_approval_modal.png`.
5. Only mark `n/a` with `ENV_DATA_MISSING:` if the lifespan log shows the stub was missing from the image (per the "Heuristic note for qv-browser" above) — never on the basis of `which pi` returning not-found.

### V7: Reload page, all tabs persist

1. Refresh the browser (`playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/"`).
2. Re-expand the AI Assistant panel.
3. **Verify:** Tab O, Tab P1, Tab P2 all reappear in the strip.
4. Click each tab and verify its prior transcript fragments are restored (chat history is per-tab and persisted in DB).
5. **Verify:** Clicking a Pi tab whose subprocess was killed (dashboard restart drops all Pi subprocesses) does not show an error; the next prompt spawns a fresh subprocess (lazy respawn).
6. Send a follow-up prompt in Tab P1 (e.g., `hello again`) and **verify** the stub responds with `Echo: hello again` (proves lazy respawn worked). Note: the bundled stub does not carry conversation history across spawns — that is a Pi-binary feature; with the stub, observing a successful response is sufficient evidence of respawn.
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
