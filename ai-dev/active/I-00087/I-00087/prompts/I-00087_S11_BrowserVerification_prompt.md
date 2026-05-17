# Browser Verification Prompt: I-00087-S11-BrowserVerification

**Work Item**: I-00087 — AI Assistant chat panel does not render model responses
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

You MUST NOT run `alembic upgrade`, `alembic upgrade <rev>`,
`alembic downgrade <anything>`, or `alembic stamp` against the live
orchestration DB. This step does not involve migrations.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, no `localhost:5173`). Always use the env var.

Do NOT hardcode application route paths. The IW AI Core dashboard runs at `/` (the project list) and the AI Assistant panel is available on every page via the global panel; prefer to land on the project list and expand the panel rather than guessing a per-project route.

Before asserting on the *content* of any page, first confirm the page itself **loaded successfully** (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors). A 500 on the page that contains the element you're verifying is itself a `code_defect` finding.

Do NOT run any of the following — they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command — the stack is already up
- `playwright install` or `npx playwright install` — the CLI is pre-installed
- `agent-browser` — this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00087/I-00087_Issue_Design.md` — the design document
- `dashboard/static/chat_assistant/chat.js` — the file the fix modified
- `tests/dashboard/test_chat_panel_event_protocol.py` — the new regression suite (your verifications complement these)

## Output Files

- `ai-dev/active/I-00087/reports/I-00087_S11_BrowserVerification_Report.md` — the mandatory report
- `ai-dev/active/I-00087/evidences/post/` — screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials (this dashboard may not require login — if the page loads directly to the project list, skip the login step and note in your report that no auth gate was encountered):

```bash
playwright-cli snapshot                       # get accessible element refs
# If a login form is present:
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00087/evidences/post/` with descriptive filenames.
4. **Screenshot path gotcha**: `playwright-cli screenshot` takes NO path argument — it always saves to `.playwright-cli/page-<ts>.png`. To name the file, snapshot first then `cp`:
   ```bash
   playwright-cli screenshot
   cp .playwright-cli/page-*.png ai-dev/active/I-00087/evidences/post/I-00087_v{N}_{name}.png
   ```

## E2E DB seed data

This work item does NOT depend on any pre-existing project/work-item rows. The AI Assistant panel is a global panel that works without any seeded data. If the project list is empty on the landing page that is fine — the panel still opens and can talk to opencode.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify)

> Automatically prepended by the qv-browser agent. Documented here for reviewers.

The agent visits the landing page (`$IW_BROWSER_BASE_URL/`) and verifies:
- HTTP 200, no exception page.
- All `hx-target`, `aria-controls`, `for=` references resolve to existing `id="X"` in the same HTML.
- No unhandled JS / HTMX errors in `.playwright-cli/console-*.log` after page load.

### V1: Send a prompt and verify the assistant's reply streams into a bubble

1. Navigate to `$IW_BROWSER_BASE_URL/` (project list — this is the landing page).
2. **Snapshot the page** and locate the ref for the **"Expand AI Assistant panel"** button. Click it.
3. Snapshot again. Locate the ref for the **`Model selector`** combobox. Confirm it has at least one option (the comprehensive fix shipped in commit `88e1ed08` populates this dropdown — if it is empty, that is an unrelated regression of the prior fix; capture it but proceed).
4. Locate the ref for the **`Ask the AI Assistant…`** textbox. Fill it with `say pong and nothing else`.
5. Locate the ref for the **`Send`** button. Click it. Rationale: this triggers `POST /api/chat/sessions/{sid}/prompt`, which kicks opencode into producing a streaming reply.
6. Wait at least **15 seconds** for opencode to generate a response (`sleep 15` in bash; opencode log shows model latency around 2–5 s but stay generous).
7. Snapshot the page.
8. **Verify:** the conversation log (`role="log"` element) contains an assistant message bubble (a `div` with class containing `chat-assistant` styling) whose text is non-empty AND is NOT the literal string `Session idle.` (that's the system status line, not the assistant reply). Use:
   ```bash
   playwright-cli eval "() => { const log = document.querySelector('[role=\"log\"]'); if (!log) return {ok:false, reason:'no log'}; const items = log.querySelectorAll('.chat-assistant-message-assistant, [data-role=\"assistant\"], .max-w-\\\\[85\\\\%\\\\].bg-secondary'); return {ok: items.length > 0, count: items.length, texts: Array.from(items).map(el => el.textContent.slice(0, 200))}; }"
   ```
   Pass criteria: `count >= 1` AND at least one entry in `texts` is non-empty AND none of the non-empty entries equals `"Session idle."` exactly.

   If the dashboard uses different DOM markers than the selector above, fall back to comparing the full `innerText` to the pre-fix evidence: an assistant reply means the text contains more than just the user prompt + `"Session idle."` line.

9. **Screenshot:** `ai-dev/active/I-00087/evidences/post/I-00087_v1_streaming_reply_rendered.png`.

### V2: Refresh the page and verify the conversation history reloads (session continuity — user-stated requirement)

1. Without closing the browser, navigate to `$IW_BROWSER_BASE_URL/` again (a normal reload) using `playwright-cli reload` or `playwright-cli goto "$IW_BROWSER_BASE_URL/"`.
2. Snapshot. Locate the **"Expand AI Assistant panel"** button (if the panel is collapsed by default after reload) and click it.
3. Wait ~3 seconds for `_loadHistory` to fetch and render past messages.
4. Snapshot.
5. **Verify:** the conversation log shows BOTH the user bubble ("say pong and nothing else") AND the assistant reply from V1. Use:
   ```bash
   playwright-cli eval "() => { const log = document.querySelector('[role=\"log\"]'); if (!log) return {ok:false}; const txt = log.innerText; return {ok: txt.includes('say pong'), userPromptVisible: txt.includes('say pong'), totalLen: txt.length, preview: txt.slice(0, 500)}; }"
   ```
   Pass criteria: `userPromptVisible === true` AND `totalLen > 50` (rough heuristic that an assistant bubble is also there — the user prompt is ~25 chars, anything beyond ~50 means content was reloaded beyond just the user line).

6. **Screenshot:** `ai-dev/active/I-00087/evidences/post/I-00087_v2_history_reload_preserves_conversation.png`.

### V3: Send a follow-up prompt in the same session (multi-turn context)

1. Locate the textbox ref (snapshot first). Fill it with `repeat your previous reply once more`.
2. Click Send. Wait 15 seconds.
3. **Verify:** a SECOND assistant bubble appears, AND the original user prompt + first assistant reply are still visible above it. This confirms the session ID was reused (same opencode session has the prior context) and that history was not wiped when the second prompt was sent.
4. **Screenshot:** `ai-dev/active/I-00087/evidences/post/I-00087_v3_multi_turn_session.png`.

### V4: No console errors during the run

1. Read `.playwright-cli/console-*.log` produced over the V0–V3 sequence.
2. **Verify:** no entries with severity `error`. Warnings are acceptable (and there may be irrelevant ones from other dashboard pages); console errors specifically from `chat.js` are NOT acceptable.
3. **Screenshot:** N/A — capture the console log file path in the report instead.

### V5: No Regressions (adjacent flows)

1. Click the **"Collapse AI Assistant panel"** button (snapshot for ref). Verify the panel collapses.
2. Re-expand. Verify the conversation is still visible (same data as V3).
3. Click the **"New chat session"** button (snapshot for ref — it's the icon button in the panel header). Verify the conversation log clears AND the model dropdown still has options.
4. Visit any other page that uses the global chat panel (e.g., `$IW_BROWSER_BASE_URL/project/iw-ai-core/` if such a project exists in the seed). Verify the panel state cleared (new tabId means new session) and the model selector still works.
5. **Screenshot:** `ai-dev/active/I-00087/evidences/post/I-00087_v5_no_regressions.png`.

## Pass Criteria

All V0..V5 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps and spec mismatches

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw console exception | CODE_DEFECT | normal `--reason` |
| Model dropdown empty in V1 step 3 | CODE_DEFECT | regression of commit 88e1ed08 — file separately if confirmed |
| Opencode model is slow (>20s) and V1 sleep is insufficient | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: opencode minimax model latency exceeded 15s timeout; verification needs longer wait or model swap"` |
| Page rendered cleanly, element correctly absent per design doc, V step asks for it anyway | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V{N} ..."` |
| Page rendered cleanly, design says element should be present, it isn't | CODE_DEFECT | normal `--reason` |

**CODE_DEFECT** — the fix-cycle agent can patch this. Use a normal `--reason`.

**ENV_DATA_MISSING** — for this work item, the most likely env gap is opencode itself being slow, mis-authenticated against the model provider (minimax token expired), or not subscribed to the configured model. In any of these cases prefix the reason with `ENV_DATA_MISSING:` and explain. The fix-cycle agent cannot fix model-provider auth; the operator needs to know.

**SPEC_MISMATCH** — if the design says "an assistant bubble must appear" but the panel's actual DOM markup uses a class name not anticipated in V1's selector, that's a spec-mismatch in this prompt's selector, not a code defect. Prefix `SPEC_MISMATCH:` and cite the offending V step.

### No cascading `n/a` — seed on demand

Do not chain V steps with "blocked by V1 — n/a". If V1 fails for ENV reasons, fail the step with that reason; do not mark V2..V5 as n/a. The orchestrator will route to the operator.

## Report

After verification, write `ai-dev/active/I-00087/reports/I-00087_S11_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V0..V5.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env).
- Any issues found, with `file:line` references if you investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V5.
- The **specific text of the assistant's V1 reply** (captured from the page DOM) — this is the most useful artifact for the human reviewer to confirm the fix worked end-to-end.

Then call one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00087/reports/I-00087_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00087/reports/I-00087_S11_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00087",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Streaming reply renders", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "evidences/post/I-00087_v1_streaming_reply_rendered.png", "notes": "Assistant reply text: <paste>"},
    {"id": "V2", "name": "History reload after refresh", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "evidences/post/I-00087_v2_history_reload_preserves_conversation.png", "notes": ""},
    {"id": "V3", "name": "Multi-turn session continuity", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "evidences/post/I-00087_v3_multi_turn_session.png", "notes": ""},
    {"id": "V4", "name": "No console errors", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions in adjacent flows", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "evidences/post/I-00087_v5_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
