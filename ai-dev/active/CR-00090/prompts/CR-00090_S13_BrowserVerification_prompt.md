# Browser Verification Prompt: CR-00090-S13-BrowserVerification

**Work Item**: CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var
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

No migration is required for this CR.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

The E2E app container was started with `IW_CORE_E2E_MODE=true` in its environment
(added to `ai-dev/iw-config/worktree-compose.template.yml` by S02 of this CR). This
means `_e2e_mode` is `True` in every template context for this stack.

Do NOT hardcode ports. Always use `$IW_BROWSER_BASE_URL`.

Before asserting on page *content*, confirm each page loaded with HTTP 200 and no
unhandled-exception page or load-time HTMX errors.

Do NOT run:
- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser`
- Any `chromium.launch()` Python/Node snippet

## Input Files

- `ai-dev/active/CR-00090/CR-00090_CR_Design.md` — Design document
- `dashboard/templates/base.html` — Contains worktree-badge with `_headless`-gated polling
- `dashboard/templates/fragments/staleness_dot.html` — Contains staleness-dot with `_headless`-gated polling
- `dashboard/templates/pages/project_selector.html` — Contains project-level badge polling

## Output Files

- `ai-dev/active/CR-00090/reports/CR-00090_S13_BrowserVerification_Report.md` — The mandatory report
- `ai-dev/active/CR-00090/evidences/post/` — Screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:
1. Always call `playwright-cli snapshot` **before** `fill` / `click`.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00090/evidences/post/` with descriptive filenames.

## Verification Steps

### V1: Polling suppressed in E2E mode — worktree-badge (AC1)

The worktree-badge element is loaded via HTMX. In E2E mode (`IW_CORE_E2E_MODE=true`),
it must render with `hx-trigger="never"` and no `hx-get` attribute, producing zero
background requests.

1. Fetch the page source that contains the worktree-badge element using curl:
   ```bash
   curl -s "$IW_BROWSER_BASE_URL/system/nav/worktree-badge" -o /tmp/worktree_badge.html
   ```
   (If the badge is embedded in the nav rather than a standalone endpoint, fetch the
   main dashboard page: `curl -s "$IW_BROWSER_BASE_URL/" -o /tmp/worktree_badge.html`)

2. Check the HTML source:
   ```bash
   grep -i "hx-trigger" /tmp/worktree_badge.html
   grep -i "hx-get" /tmp/worktree_badge.html
   ```

3. **Verify:**
   - `hx-trigger` value is `"never"` (or the element has no polling trigger)
   - The worktree-badge element does NOT have a `hx-get` attribute pointing to a polling endpoint

4. Open the page in the browser and check the console log for connection errors:
   ```bash
   playwright-cli open "$IW_BROWSER_BASE_URL"
   ```
   Wait ~5 seconds for any polling to fire, then:
   ```bash
   cat .playwright-cli/console-*.log 2>/dev/null | grep -i "ERR_CONNECTION\|sendError\|htmx" | head -20
   ```

5. **Verify:** The console log contains NO `ERR_CONNECTION_REFUSED` or `htmx:sendError` entries related to the worktree-badge or staleness-dot endpoints.

6. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/CR-00090/evidences/post/CR-00090_v1_polling_suppressed.png`

### V2: Polling suppressed — staleness-dot (AC1)

1. Navigate to the project dashboard page (find a project from the selector or navigate to a project's dashboard URL):
   ```bash
   playwright-cli open "$IW_BROWSER_BASE_URL"
   ```
   Then click through to a project dashboard.

2. Fetch the staleness-dot fragment source:
   ```bash
   # Get the project id from the page URL or snapshot
   curl -s "$IW_BROWSER_BASE_URL/projects/<project_id>/staleness-dot" -o /tmp/staleness_dot.html
   ```

3. Check the HTML source:
   ```bash
   grep -i "hx-trigger" /tmp/staleness_dot.html
   grep -i "hx-get" /tmp/staleness_dot.html
   ```

4. **Verify:**
   - `hx-trigger` value is `"never"` (or no trigger present)
   - No `hx-get` on the polling element

5. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/CR-00090/evidences/post/CR-00090_v2_staleness_dot_suppressed.png`

### V3: Navigation works correctly with polling suppressed (AC6)

Verify that suppressing polling does not break normal navigation or page rendering.

1. Navigate through several dashboard pages:
   - Project selector: `$IW_BROWSER_BASE_URL`
   - A project's history page
   - A project's batches page

2. For each page, take a snapshot and confirm:
   - The page renders without a 500 error or unhandled-exception page
   - Core UI elements (nav, tables, or list items) are visible

3. **Verify:** No `Jinja2 UndefinedError` for `_e2e_mode` in any page (would appear as a 500 error or template exception in the response)

4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/CR-00090/evidences/post/CR-00090_v3_nav_no_regressions.png`

### V4: No console errors (AC1, AC6)

After completing V1–V3, review all console logs accumulated during the browser session:

```bash
cat .playwright-cli/console-*.log 2>/dev/null | grep -iE "ERR_CONNECTION|sendError|htmx:send|HTMX" | head -30
```

**Verify:** Zero occurrences of `ERR_CONNECTION_REFUSED` or `htmx:sendError` for the
worktree-badge or staleness-dot polling endpoints. Some HTMX log entries (e.g., page-load
requests that return 200) are acceptable — only connection errors are a failure.

**Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/CR-00090/evidences/post/CR-00090_v4_no_console_errors.png`

## Pass Criteria

All V1..V4 must pass. Any failure — including console connection errors — requires
calling `iw step-fail`.

| Failure shape | Class |
|---|---|
| Page returned 5xx or `UndefinedError` for `_e2e_mode` | CODE_DEFECT |
| `ERR_CONNECTION_REFUSED` on polling endpoints | CODE_DEFECT (polling not suppressed) |
| Polling attributes present when `IW_CORE_E2E_MODE=true` | CODE_DEFECT |
| Page rendered but project data absent from seed | ENV_DATA_MISSING |

## Report

After verification, write `ai-dev/active/CR-00090/reports/CR-00090_S13_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V4
- The exact `$IW_BROWSER_BASE_URL` used
- Any issues found with `file:line` references
- List of screenshots captured (relative paths under `evidences/post/`)
- **No regressions observed** subsection

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00090/reports/CR-00090_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00090/reports/CR-00090_S13_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "CR-00090",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "<actual URL from $IW_BROWSER_BASE_URL>",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Polling suppressed — worktree-badge", "status": "pass|fail", "failure_class": null, "screenshot": "evidences/post/CR-00090_v1_polling_suppressed.png", "notes": ""},
    {"id": "V2", "name": "Polling suppressed — staleness-dot", "status": "pass|fail", "failure_class": null, "screenshot": "evidences/post/CR-00090_v2_staleness_dot_suppressed.png", "notes": ""},
    {"id": "V3", "name": "Navigation works with polling suppressed", "status": "pass|fail", "failure_class": null, "screenshot": "evidences/post/CR-00090_v3_nav_no_regressions.png", "notes": ""},
    {"id": "V4", "name": "No console errors", "status": "pass|fail", "failure_class": null, "screenshot": "evidences/post/CR-00090_v4_no_console_errors.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
