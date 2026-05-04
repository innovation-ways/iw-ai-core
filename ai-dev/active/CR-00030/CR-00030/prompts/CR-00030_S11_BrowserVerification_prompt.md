# Browser Verification Prompt: CR-00030-S11-BrowserVerification

**Work Item**: CR-00030 -- Show remaining time (not end time) on Claude 5h usage slot
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

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

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

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:9900`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment.

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/CR-00030/CR-00030_CR_Design.md` -- the design document
- `orch/llm_usage.py`
- `tests/unit/test_llm_usage.py`
- `dashboard/templates/fragments/llm_usage_footer.html` (read-only — verify visually that the template renders the new string)

## Output Files

- `ai-dev/active/CR-00030/reports/CR-00030_S11_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00030/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

The IW AI Core dashboard does not require login (no auth middleware on the global routes). If the launched stack does prompt for `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`, log in following the standard pattern:

```bash
playwright-cli snapshot                       # get accessible element refs (e10, e12, ...)
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00030/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB
via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`).

The Claude usage label is rendered server-side from `~/.claude/rate-limits-cache.json` on the host that runs the dashboard process — NOT from the database. The verification therefore depends on the existence and freshness of that cache file in the worktree's runtime environment, not on DB seed data.

If the cache file is missing or stale, the dashboard will render the static `5h` placeholder for the Claude column. That is the **AC5** branch and you may verify it as one of the cases (V3). The other cases (V1, V2) require the cache to be present with a future `resets_at` — see the directions in V1 and V2 below for how to synthesise this.

If you cannot satisfy V1 or V2 because the cache file cannot be controlled in the E2E stack, classify the failure as `ENV_DATA_MISSING` per the standard QV Browser contract.

## Verification Steps

### V1: Claude 5h slot label is in the new "Xh Ym" form

1. From a shell, write a controlled `~/.claude/rate-limits-cache.json` whose `five_hour.resets_at` is exactly `now + 4h 32m` (Unix epoch seconds, UTC) and `five_hour.used_percentage` is `8`. Likewise set `seven_day.resets_at` to `now + 3 days` and `seven_day.used_percentage` to `15`. Use the same key names already produced by the Claude Code statusline hook (see `orch/llm_usage.py` lines 70-91 for the exact shape).
2. Navigate to `$IW_BROWSER_BASE_URL/`.
3. Wait for the footer to refresh (htmx polls `/api/usage/llm/fragment` every 60s; you can also force an immediate refresh by reloading the page — the in-process `_cache` TTL is 60s, so reloading more than 60s after writing the cache is the most reliable path).
4. **Verify:** The footer's Claude column contains text matching the regex `^\d+h \d+m$` (e.g. `4h 32m`) immediately to the LEFT of the 5h progress bar. The percentage immediately to the RIGHT of the bar still reads `8%`.
5. **Verify:** The text does NOT contain a colon (`:`) in the 5h column — that would be the old wall-clock format.
6. **Screenshot:** `ai-dev/active/CR-00030/evidences/post/CR-00030_v1_5h_remaining.png`.

### V2: Claude 7d slot label is unchanged (wall-clock)

1. With the same cache file from V1 (which set `seven_day.resets_at` to `now + 3 days`), inspect the footer's Claude 7d column.
2. **Verify:** The label to the LEFT of the 7d progress bar matches `^[A-Z][a-z]{2} \d{2}:\d{2}$` (e.g. `Tue 09:00`) — the existing `_format_resets_at` output for `>=24h`. The percentage to the RIGHT reads `15%`.
3. **Verify:** The 7d label DOES contain a colon. (This is the inverse of V1's negative assertion and confirms the 7d branch was not accidentally changed.)
4. **Screenshot:** `ai-dev/active/CR-00030/evidences/post/CR-00030_v2_7d_unchanged.png`.

### V3: Sub-hour Claude 5h label uses minutes only

1. Rewrite `~/.claude/rate-limits-cache.json` with `five_hour.resets_at = now + 25 minutes` (and any non-zero `used_percentage`). Leave `seven_day` as in V1.
2. Wait > 60s OR clear the in-process `_cache` (a dashboard restart is NOT in scope — instead, simply wait for the next htmx poll, which is at most 60s).
3. **Verify:** The Claude 5h label matches `^\d+m$` (e.g. `25m`) and does NOT contain `h ` (no hour component).
4. **Screenshot:** `ai-dev/active/CR-00030/evidences/post/CR-00030_v3_5h_minutes_only.png`.

### V4: Missing cache → static "5h" placeholder

1. Move or delete `~/.claude/rate-limits-cache.json` (rename to `rate-limits-cache.json.bak` so it can be restored).
2. Wait > 60s for the next htmx poll OR reload the page.
3. **Verify:** The Claude 5h label reads exactly `5h` (the template's `or '5h'` fallback) and the percentage reads `0%`.
4. Restore the cache file (move the `.bak` back) so the system continues to work normally for the rest of verification.
5. **Screenshot:** `ai-dev/active/CR-00030/evidences/post/CR-00030_v4_5h_placeholder.png`.

### V5: No Regressions

1. Open the browser console BEFORE step 2 so any error is captured.
2. Navigate to `$IW_BROWSER_BASE_URL/` and let the page fully load.
3. Visit at least two other pages: `$IW_BROWSER_BASE_URL/system/status` and any project page (e.g. `$IW_BROWSER_BASE_URL/project/iw-ai-core/`).
4. **Verify:** No new console errors on any page visited during V1..V4. Specifically: no `TypeError` related to `claude_reset`, no `TemplateSyntaxError`, no 500 responses on `/api/usage/llm/fragment`.
5. **Verify:** The MiniMax row in the same footer continues to display correctly (e.g. its label still matches `^\d+h \d+m$|^\d+m$|^5h$`). This confirms the change did not accidentally break the unrelated MiniMax helper.
6. **Screenshot:** `ai-dev/active/CR-00030/evidences/post/CR-00030_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed".

### Distinguishing code defects from environment gaps

Before failing the step, classify the failure:

- **CODE DEFECT** -- the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** -- the verification cannot be set up because the E2E stack does not allow controlling `~/.claude/rate-limits-cache.json` (e.g. it runs in a sandbox without HOME write access). Prefix the reason with `ENV_DATA_MISSING:`. The fix-cycle agent **cannot** fix this by editing code.

## Report

After verification, write `ai-dev/active/CR-00030/reports/CR-00030_S11_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if root cause was investigated.
- A list of the screenshots captured under `evidences/post/`.
- A **No regressions observed** subsection covering the MiniMax row and the additional pages visited in V5.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00030/reports/CR-00030_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00030/reports/CR-00030_S11_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "CR-00030",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Claude 5h label in 'Xh Ym' form", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Claude 7d label unchanged", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Sub-hour 5h label minutes-only", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Missing cache -> '5h' placeholder", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions (console, MiniMax, adjacent pages)", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed. `fail` on any failure.
- `base_url_used`: The concrete URL the agent actually hit.
- `console_errors_observed`: Any console errors seen during any V(n), even if the verification otherwise passed. A non-empty list on a passing run should be flagged in the report.
