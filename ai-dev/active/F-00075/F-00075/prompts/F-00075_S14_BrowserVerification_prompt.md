# Browser Verification Prompt: F-00075-S14-BrowserVerification

**Work Item**: F-00075 -- MiniMax Coding Plan usage from /coding_plan/remains (replace local SQLite estimate)
**Step**: S14
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

This work item touches no migrations.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, no `localhost:3100`). Always use the env var.

Do NOT run any of the following:

- `make dev`, `make test-e2e`, `make e2e-up`, `docker compose ...` -- the stack is already up.
- `playwright install` or `npx playwright install` -- the CLI is pre-installed.
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**.
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`.

## Input Files

- `ai-dev/active/F-00075/F-00075_Feature_Design.md` -- design document.
- `ai-dev/active/F-00075/evidences/pre/F-00075-before-fragment.html` -- the wrong "before" output (MiniMax 19%, no reset countdown).
- Files modified by implementation steps:
  - `orch/llm_usage.py`
  - `dashboard/routers/usage.py`
  - `dashboard/templates/fragments/llm_usage_footer.html`

## Output Files

- `ai-dev/active/F-00075/reports/F-00075_S14_BrowserVerification_Report.md` -- mandatory report.
- `ai-dev/active/F-00075/evidences/post/` -- screenshots taken during verification.

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in (the worktree stack uses session auth):

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

If the login screen is not present (some E2E configurations skip auth), proceed directly. Document this in the report.

Rules:
1. Always call `playwright-cli snapshot` **before** `fill` / `click`.
2. Wait for navigation to settle before snapshotting again.
3. Screenshots: run `playwright-cli screenshot` (no path argument), then `cp .playwright-cli/page-*.png ai-dev/active/F-00075/evidences/post/F-00075_v{N}_{short_name}.png`. **Do not** pass a path to `playwright-cli screenshot` — it will be misinterpreted as an element ref.

## E2E DB seed data

This feature is purely about footer UI computed from a live external API call. No DB seed fixtures are required.

The E2E stack will use the same MiniMax API key resolution chain (`IW_MINIMAX_API_KEY` env var → `~/.local/share/opencode/auth.json`) that the production code uses. If the worktree stack does not have a key configured, the verifications below should still pass for the **failure-path branch** (V3) but the success-path branches (V1, V2) will be inconclusive — call `iw step-fail` with reason `ENV_DATA_MISSING: MiniMax API key not configured in worktree stack; cannot verify success-path AC1/AC2`.

## Verification Steps

### V1: MiniMax footer bar shows the live percentage

1. Navigate to `$IW_BROWSER_BASE_URL/`.
2. Wait for the page to settle (the htmx-driven footer fragment polls every 60 seconds; the first render happens shortly after page load). The MiniMax row appears in the footer at the bottom of every page.
3. **Verify**: The footer contains the literal text `MiniMax`, followed by a reset label (matches `\dh \dm` like `"2h 43m"`, or `\dm` like `"45m"`, or the fallback `"5h"`), a coloured bar, and a percentage. The percentage value must equal what the live API returns:

   ```bash
   KEY="${IW_MINIMAX_API_KEY:-$(python3 -c "import json; print(json.load(open('/home/sergiog/.local/share/opencode/auth.json'))['minimax']['key'])" 2>/dev/null)}"
   if [ -n "$KEY" ]; then
     curl -s -H "Authorization: Bearer $KEY" -H "Accept: application/json" \
       https://api.minimax.io/v1/api/openplatform/coding_plan/remains \
       | python3 -c "import json,sys; d=json.load(sys.stdin); r=next(r for r in d['model_remains'] if r['model_name']=='MiniMax-M*'); used=r['current_interval_total_count']-r['current_interval_usage_count']; print(round(used/r['current_interval_total_count']*100) if r['current_interval_total_count'] else 0)"
   fi
   ```

   Compare the `<percentage>%` text in the footer against this output (allow ±1 due to integer rounding). They must agree.
4. **Screenshot**: `ai-dev/active/F-00075/evidences/post/F-00075_v1_minimax_live_percent.png`.

### V2: Reset countdown renders next to the MiniMax bar

1. Inspect the rendered footer (you may use `playwright-cli snapshot` to get the accessibility tree, or fetch `$IW_BROWSER_BASE_URL/api/usage/llm/fragment` via `curl -s`).
2. **Verify**: the MiniMax row contains a reset label that matches the regex `^(\d+h \d+m|\d+m|5h)$`. The literal `"5h"` is acceptable only if the API call returned no `block_reset` (failure path); otherwise the value must be a real countdown.
3. **Verify**: When the API call succeeded, the value of the countdown is consistent with the MiniMax response's `remains_time` field. Allow up to ±2 minutes drift between the API call and the dashboard render due to the 60s in-process cache.
4. **Screenshot**: `ai-dev/active/F-00075/evidences/post/F-00075_v2_minimax_reset_label.png`.

### V3: Failure path renders 0% with no exception (graceful degradation)

1. Temporarily make the remote call fail by either (a) unsetting the MiniMax key in the worktree environment if you have access, or (b) writing a temporary monkeypatch via the running dashboard's debug endpoint if available, or (c) simulating by reading the rendered fragment when the configured endpoint is unreachable. If none of these are feasible in the worktree stack, **skip V3** and document why in the report — this case is already covered by unit tests (S07).
2. If you can simulate the failure: navigate to `$IW_BROWSER_BASE_URL/`, force a footer refresh.
3. **Verify**: MiniMax row reads `0%`, no JavaScript console errors, no HTTP 500 from `/api/usage/llm/fragment`.
4. **Screenshot**: `ai-dev/active/F-00075/evidences/post/F-00075_v3_minimax_failure_zero.png` (if simulated; otherwise note "covered by unit tests, no V3 evidence captured").

### V4: Claude row unchanged (no regression)

1. Inspect the same rendered footer.
2. **Verify**: The Claude row still contains its 5h bar with reset label and the 7d weekly bar. Both percentages render. The Claude region is unchanged from the pre-evidence file.
3. Compare against `ai-dev/active/F-00075/evidences/pre/F-00075-before-fragment.html` for the Claude segment specifically — it should be byte-identical except for the dynamic percentage values.
4. **Screenshot**: `ai-dev/active/F-00075/evidences/post/F-00075_v4_claude_unchanged.png`.

### V5: No Regressions

1. Visit at least three other pages in the dashboard (e.g. `/system/status`, a project's queue page, a project's docs page) and confirm the footer renders consistently on each — same MiniMax row layout, no console errors, no HTTP 500s on `/api/usage/llm/fragment`.
2. Verify no new console errors appeared on any page visited during V1..V4.
3. **Screenshot**: `ai-dev/active/F-00075/evidences/post/F-00075_v5_no_regressions.png`.

## Pass Criteria

V1, V2, V4, V5 must all pass. V3 is a "best effort" verification — if it cannot be simulated in the worktree stack, document the inability and rely on the S07 unit tests for failure-path coverage; this does **not** fail the step.

If V1's percentage disagrees with the live API by more than ±1, fail the step with `--reason "V1: footer % does not match live MiniMax API (footer=X%, api=Y%)"` and screenshot both.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — wrong percentage, missing reset label, console error on the fragment, HTTP 500 from the route. Use a normal `--reason`.
- **ENV_DATA_MISSING** — MiniMax API key is not configured in the worktree stack so V1/V2 cannot be verified against a real API response. Prefix the reason with `ENV_DATA_MISSING:` so the daemon recognises it as an environment gap, not a code defect:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: worktree stack has no IW_MINIMAX_API_KEY and no opencode auth.json — cannot verify V1/V2 against live API" \
    --report ai-dev/active/F-00075/reports/F-00075_S14_BrowserVerification_Report.md
  ```

## Report

Write `ai-dev/active/F-00075/reports/F-00075_S14_BrowserVerification_Report.md` with:

- Pass/fail table for V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- The footer percentage observed and the live API percentage observed (V1 evidence).
- The reset countdown text observed (V2 evidence).
- File:line references if root-cause investigation was performed.
- List of all screenshots in `evidences/post/`.
- A "**No regressions observed**" subsection summarising V4 + V5.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00075/reports/F-00075_S14_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00075/reports/F-00075_S14_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "F-00075",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "MiniMax footer bar shows live percentage", "status": "pass|fail|skipped", "screenshot": "F-00075_v1_minimax_live_percent.png", "notes": ""},
    {"id": "V2", "name": "Reset countdown renders", "status": "pass|fail|skipped", "screenshot": "F-00075_v2_minimax_reset_label.png", "notes": ""},
    {"id": "V3", "name": "Failure path renders 0% gracefully", "status": "pass|fail|skipped", "screenshot": "F-00075_v3_minimax_failure_zero.png", "notes": ""},
    {"id": "V4", "name": "Claude row unchanged", "status": "pass|fail|skipped", "screenshot": "F-00075_v4_claude_unchanged.png", "notes": ""},
    {"id": "V5", "name": "No regressions on other pages", "status": "pass|fail|skipped", "screenshot": "F-00075_v5_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
