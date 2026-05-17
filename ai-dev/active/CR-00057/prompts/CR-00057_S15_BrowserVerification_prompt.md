# Browser Verification Prompt: CR-00057-S15-BrowserVerification

**Work Item**: CR-00057 — AI Assistant chat model allowlist (per-project, with Ollama provider)
**Step**: S15
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Standard policy. The isolated E2E stack is already up — do **not** run any `docker compose` or `make dev` / `make e2e-up` command. Use `docker compose -p "$COMPOSE_PROJECT_NAME" exec app …` only if you need to re-seed.

## ⛔ Migrations: agents generate, daemon applies

This CR doesn't add or modify any migration. The allowlist is JSONB inside `Project.config`. No migration concerns here.

## Environment

The IW orchestrator has already started an isolated E2E stack built from this worktree's source. Read the runtime env vars:

- Base URL: `$IW_BROWSER_BASE_URL`
- E2E credentials: `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
- Work item / step identifiers: `$IW_ITEM_ID` / `$IW_STEP_ID`

Do **not** hardcode ports or URLs. Always use `$IW_BROWSER_BASE_URL`.

Do **not** run `make dev`, `make e2e-up`, `docker compose up/down`, `playwright install`, `agent-browser`, or direct `chromium.launch()`. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/CR-00057/CR-00057_CR_Design.md`
- `dashboard/routers/chat.py` (modified by S02)
- `dashboard/static/chat_assistant/chat.js` (modified by S03)
- `projects.toml` (modified by S05 — seeded `[projects.iw-ai-core.ai_assistant]` block)

## Output Files

- `ai-dev/active/CR-00057/reports/CR-00057_S15_BrowserVerification_Report.md`
- `ai-dev/active/CR-00057/evidences/post/*.png`

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
playwright-cli snapshot      # get refs for login form
playwright-cli fill <user-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <pwd-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-ref>
```

If the dashboard does not require login in the E2E stack, skip the login step — the snapshot will tell you.

## E2E seed data

The E2E DB is seeded via `pg_dump` from the production orch DB plus `scripts/e2e_seed.py` baseline. For this CR you need exactly one thing in the seed: a `Project` row with `id='iw-ai-core'` whose `config["ai_assistant"]` matches the seeded allowlist (5 models, default `anthropic/claude-opus-4-7`).

If the seeded DB lacks this row or the `ai_assistant` config key:

1. Confirm by hitting `${IW_BROWSER_BASE_URL}/api/chat/config?project_id=iw-ai-core` directly with `curl` from the host and checking the response. (`curl -fsS "${IW_BROWSER_BASE_URL}/api/chat/config?project_id=iw-ai-core"`).
2. If `models` is the full opencode flatten instead of the curated 5, the row's config wasn't synced. Trigger the registry sync inside the app container:

   ```bash
   docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
     uv run python -c "from orch.daemon.project_registry import sync_projects_from_toml; from orch.db.session import SessionLocal; \
       sess = SessionLocal(); sync_projects_from_toml(sess); sess.commit()"
   ```

3. If the sync function name differs, read `orch/daemon/project_registry.py` to find the public entry point and adjust. Document any deviation in the report.

## Verification Steps

### V0: Pre-flight page sanity (built-in)

Handled automatically by qv-browser. Do not add anything here.

### V1: AI Assistant dropdown shows the curated 5-model allowlist on iw-ai-core

1. Navigate to `${IW_BROWSER_BASE_URL}/project/iw-ai-core/`.
2. Click the "Expand AI Assistant panel" rail button (the collapsed rail on the left edge) — this opens the panel and triggers `_loadConfig()` which fetches `/api/chat/config?project_id=iw-ai-core`.
3. **Verify** the model `<select id="chat-assistant-model">` element contains **exactly** five `<option>` entries, in this order, with the first one `[selected]`:
   - `anthropic/claude-opus-4-7`
   - `anthropic/claude-sonnet-4-6`
   - `minimax/MiniMax-M2.7`
   - `openai/gpt-5.3-codex`
   - `ollama/gemma4:26b`
4. **Verify** no console errors fired during the panel mount (check `.playwright-cli/console-*.log`).
5. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/CR-00057/evidences/post/CR-00057_v1_dropdown_filtered.png`.

### V2: `/api/chat/config?project_id=iw-ai-core` returns the curated list

1. From the host, run:

   ```bash
   curl -fsS "${IW_BROWSER_BASE_URL}/api/chat/config?project_id=iw-ai-core" | python -m json.tool
   ```

2. **Verify** the JSON shape is `{"models": [...], "default_model": "...", "default_agent": "..."}`.
3. **Verify** `models` is exactly the 5 entries in order.
4. **Verify** `default_model == "anthropic/claude-opus-4-7"`.
5. Save the captured JSON to `ai-dev/active/CR-00057/evidences/post/CR-00057_v2_api_response.json`.
6. **Screenshot:** N/A for this V (pure API check); include the JSON file in the evidence list instead.

### V3: Fail-open on a system page (no project_id)

1. Navigate to `${IW_BROWSER_BASE_URL}/system/status`.
2. Expand the AI Assistant panel.
3. Inspect the network call made by `chat.js` and **verify** the URL is `/api/chat/config` (no `?project_id=` query parameter). Use `playwright-cli` to read the page's HTML/JS state or directly snapshot the dropdown.
4. **Verify** the `<select id="chat-assistant-model">` element contains many more than 5 entries (the unfiltered fail-open list). Exact count is fine; what matters is that it is NOT the curated 5.
5. **Screenshot:** `ai-dev/active/CR-00057/evidences/post/CR-00057_v3_fail_open_system_page.png`.

### V4: Switching projects refreshes the dropdown

1. From `${IW_BROWSER_BASE_URL}/project/iw-ai-core/` with the panel expanded and showing the curated 5, navigate (via the project switcher in the nav, not a hard reload) to a project that has no `[ai_assistant]` block (e.g. `innoforge` if seeded; otherwise pick any other project in `projects.toml`).
2. Wait for the page transition to settle. The chat panel persists across the htmx swap.
3. Within 30 s (cache TTL boundary) or on the next refresh tick of `_modelRefreshTimer`, **verify** the dropdown now reflects the new project — either the curated list for that project, or the fail-open full list if it has no allowlist.
4. **Screenshot:** `ai-dev/active/CR-00057/evidences/post/CR-00057_v4_project_switch.png`.
5. If V4 cannot be satisfied because the test data has only one project with an allowlist, document the constraint and mark V4 as `n/a` with the reason `ENV_DATA_MISSING: no second project with deterministic allowlist state in seed` and call `iw step-fail` with that prefix.

### V5: Send a prompt with the default model

1. Back on `${IW_BROWSER_BASE_URL}/project/iw-ai-core/` with the panel expanded.
2. Type `"hello"` into the composer textarea and submit.
3. **Verify** an assistant message appears within 30 s. The content of the response is irrelevant; the goal is to prove the round-trip works under the curated default (`anthropic/claude-opus-4-7`). If the assistant returns an error event (e.g. `401 Unauthorized` because the E2E stack lacks Anthropic credentials), this is `ENV_DATA_MISSING` — document it and DO NOT fail the step as a code defect. The credentials gap is operator-owned; for verification purposes V1+V2+V3 are sufficient acceptance.
4. **Screenshot:** `ai-dev/active/CR-00057/evidences/post/CR-00057_v5_prompt_roundtrip.png`.

### V6: No Regressions

1. From `${IW_BROWSER_BASE_URL}/project/iw-ai-core/`, navigate to the Code tab, the Docs tab, and the Jobs tab. **Verify** none of them log unhandled JS or HTMX errors.
2. Open `playwright-cli snapshot` on each page and confirm the chat panel is still mounted and expandable.
3. **Verify** no console errors appeared on any page visited during V1..V5.
4. **Screenshot:** `ai-dev/active/CR-00057/evidences/post/CR-00057_v6_no_regressions.png`.

## Pass Criteria

V1, V2, V3, V6 must all pass. V4 may be `n/a` with an `ENV_DATA_MISSING:` reason if the seed lacks a second project. V5 may be `n/a` with an `ENV_DATA_MISSING:` reason if the E2E stack lacks the Anthropic credentials to actually invoke the model. Any other failure pattern is a `code_defect` — fail the step with a normal `--reason`.

## Report

Write `ai-dev/active/CR-00057/reports/CR-00057_S15_BrowserVerification_Report.md` containing:

- The pass/fail table per V1..V6.
- The exact `$IW_BROWSER_BASE_URL` used.
- A list of evidence files captured under `evidences/post/`.
- A "No regressions observed" subsection covering the Code / Docs / Jobs tabs from V6.

Then call:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00057/reports/CR-00057_S15_BrowserVerification_Report.md

# On failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00057/reports/CR-00057_S15_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "CR-00057",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "<actual url from env>",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Curated 5-model allowlist on iw-ai-core", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "/api/chat/config returns curated list", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Fail-open on system page", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Project switch refreshes dropdown", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Prompt round-trip with default model", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No regressions across project tabs", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
