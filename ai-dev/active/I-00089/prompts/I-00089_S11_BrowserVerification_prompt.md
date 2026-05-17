# Browser Verification Prompt: I-00089-S11-BrowserVerification

**Work Item**: I-00089 -- AI Assistant panel — in-header collapse button is unusable in both states
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

  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.
  4. `docker compose exec app …` is allowed when re-running an
     `e2e_fixtures` seed inside the already-running stack (not needed here —
     this incident has no fixtures).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp. Not needed for this step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD` — NOT required for this incident (the dashboard root `/` is unauthenticated; the AI Assistant panel renders on every page).
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, no `localhost:5173`). Always use `$IW_BROWSER_BASE_URL`. Do NOT hardcode route paths — navigate from the root and use whatever URL the dashboard actually serves.

Do NOT run any of the following:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose up/down/restart` -- the stack is already up.
- `playwright install` or `npx playwright install` -- the CLI is pre-installed.
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**.
- Any `chromium.launch()` snippet -- always go through `playwright-cli`.

## Input Files

- `ai-dev/active/I-00089/I-00089_Issue_Design.md` -- the design document with the canonical Browser Verification Script
- `dashboard/templates/chat_assistant/panel.html` -- as modified by S01
- `dashboard/static/chat_assistant/chat.css` -- as modified by S01
- `ai-dev/active/I-00089/evidences/pre/` -- pre-fix screenshots and DOM snapshots for direct visual comparison

## Output Files

- `ai-dev/active/I-00089/reports/I-00089_S11_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/I-00089/evidences/post/` -- screenshots and YAML snapshots captured during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

No login step is required — the panel renders on every dashboard page including the unauthenticated root.

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element refs.
2. Wait for navigation/transitions to settle before snapshotting again. The panel uses a CSS transition (`transition: width 0.2s ease-in-out` in `chat.css:10`); allow at least 0.5 s after a click before snapshotting.
3. Screenshots go under `ai-dev/active/I-00089/evidences/post/` with descriptive filenames.
4. `playwright-cli screenshot` takes NO path arg — it writes to `.playwright-cli/page-<ts>.png`. Move/copy with `cp .playwright-cli/page-*.png ai-dev/active/I-00089/evidences/post/<name>.png`.

## E2E DB seed data

This incident has NO E2E fixture dependency. The fix is purely HTML/CSS — the panel renders identically against any seeded DB. No `ai-dev/active/I-00089/e2e_fixtures/` files exist, and none are needed.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

The agent prepends V0 unconditionally — visit every distinct route referenced in V1..V(n) and check for dangling fragment refs and console errors. Documented for design reviewers.

### V1: Collapsed state — no stray "<" button

1. Navigate to `$IW_BROWSER_BASE_URL/`.
2. Wait for the page to fully load.
3. **Verify** (DOM): `playwright-cli snapshot` — inside the `region "AI Assistant chat"`, only the `Expand AI Assistant panel (Ctrl+/)` affordance is present. There MUST NOT be a `Collapse AI Assistant panel (Ctrl+/)` button reported in the snapshot (the pre-fix snapshot at `ai-dev/active/I-00089/evidences/pre/I-00089-bug-A-collapsed-snapshot.yml` shows BOTH buttons in the collapsed region — this is what the fix removes).
4. **Verify** (visual): `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00089/evidences/post/I-00089_v1_collapsed_no_stray_chevron.png`. The 40-pixel-wide rail at the left edge of the page shows ONLY the vertical "AI Assistant" tab with the ">" expand chevron. There is no "<" chevron above it.
5. **Failure class hint**: if the `Collapse AI Assistant panel` button is still in the snapshot's collapsed-region list, that is a CODE_DEFECT (S01's `<style>` block extension didn't land).

### V2: Expanded state — collapse button is discoverable

1. Click the `Expand AI Assistant panel (Ctrl+/)` button (read its ref from the latest snapshot, do not reuse from V1).
2. Wait 0.5 s for the width transition.
3. `playwright-cli snapshot` and locate the `Collapse AI Assistant panel (Ctrl+/)` button. Confirm it is now in the expanded panel's header alongside the tray-toggle, history-toggle, and new-btn buttons.
4. **Verify** (rendered HTML): fetch the page HTML via `curl -s "$IW_BROWSER_BASE_URL/" | grep -A2 'chat-assistant-collapse-btn'` and confirm the button tag carries a `title="..."` attribute AND either the custom class `chat-assistant-collapse-btn-distinct` OR a Tailwind border utility (`border` or `border-l`). One of these MUST be present.
5. **Verify** (visual): `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00089/evidences/post/I-00089_v2_expanded_collapse_button_visible.png`. The collapse "<" icon in the header is visually distinct from the three icons to its left — it has a visible border, background, or separator that makes it stand out as the collapse affordance.
6. **Failure class hint**: if no `title` attribute and no distinguishing class marker are present on the button tag, that is a CODE_DEFECT (S01's Bug B fix didn't land).

### V3: Clicking the collapse button actually collapses

1. From the expanded state (post-V2), click the `Collapse AI Assistant panel (Ctrl+/)` button (read its current ref from a fresh snapshot).
2. Wait 0.5 s for the width transition.
3. `playwright-cli snapshot` — confirm the panel is now in the collapsed state (only the `Expand AI Assistant panel` affordance is reported in the region).
4. `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/I-00089/evidences/post/I-00089_v3_collapse_button_collapses.png`.
5. **Failure class hint**: if the panel does not collapse, that is a CODE_DEFECT (the JS handler at `chat.js:953-956` is broken — but S01 should not have touched the JS at all).

### V4: No Regressions

1. Verify the Ctrl+/ keyboard shortcut still toggles the panel:
   - Open the page fresh (`playwright-cli open "$IW_BROWSER_BASE_URL"`).
   - Use playwright-cli's keyboard binding to send Ctrl+/ (if not supported by the CLI, document the limitation in the report and skip this check; do NOT fail the step on a CLI capability gap).
2. Verify the nav-bar `Toggle AI Assistant panel (Ctrl+/)` button (top of the page header, ref `e70` in pre-fix snapshots) still toggles the panel — click it and snapshot before/after.
3. Verify no new console errors appeared on any page visited during V1..V3. Read `.playwright-cli/console-*.log` if available.
4. `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/I-00089/evidences/post/I-00089_v4_no_regressions.png`.

## Pass Criteria

All V1..V4 must pass. Any failure requires calling `iw step-fail` with a reason and the report path.

### Distinguishing code defects from environment gaps and spec mismatches

This incident has no E2E fixture dependency, so `ENV_DATA_MISSING` is unlikely. The most likely failure shapes are:

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx | CODE_DEFECT | normal `--reason`, capture traceback |
| `Collapse AI Assistant panel` still in collapsed-region snapshot | CODE_DEFECT | S01 didn't extend the `<style>` block; normal `--reason` |
| Collapse button missing `title` OR distinguishing class | CODE_DEFECT | S01's Bug B fix didn't land; normal `--reason` |
| Clicking collapse button doesn't collapse the panel | CODE_DEFECT | S01 broke something else; normal `--reason` |
| Ctrl+/ doesn't toggle (and playwright-cli can send the key) | CODE_DEFECT | S01 modified the JS keybind by mistake; normal `--reason` |
| playwright-cli can't send Ctrl+/ programmatically | tooling gap | document in notes, do NOT fail the step |

## Report

After verification, write `ai-dev/active/I-00089/reports/I-00089_S11_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V4.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of all screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection confirming Ctrl+/ and the nav-bar toggle still work.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00089/reports/I-00089_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00089/reports/I-00089_S11_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00089",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Collapsed state — no stray '<' button", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "evidences/post/I-00089_v1_collapsed_no_stray_chevron.png", "notes": ""},
    {"id": "V2", "name": "Expanded state — collapse button is discoverable", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "evidences/post/I-00089_v2_expanded_collapse_button_visible.png", "notes": ""},
    {"id": "V3", "name": "Clicking the collapse button actually collapses", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "evidences/post/I-00089_v3_collapse_button_collapses.png", "notes": ""},
    {"id": "V4", "name": "No regressions (Ctrl+/, nav-bar toggle, no console errors)", "status": "pass|fail|n/a", "failure_class": "code_defect|null", "screenshot": "evidences/post/I-00089_v4_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "evidences/post/I-00089_v1_collapsed_no_stray_chevron.png",
    "evidences/post/I-00089_v2_expanded_collapse_button_visible.png",
    "evidences/post/I-00089_v3_collapse_button_collapses.png",
    "evidences/post/I-00089_v4_no_regressions.png"
  ],
  "notes": ""
}
```
