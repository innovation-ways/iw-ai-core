# Browser Verification Prompt: I-00040-S13-BrowserVerification

**Work Item**: I-00040 -- Alembic-version guard at daemon/dashboard/launch boundaries
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

  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch
DB on port 5433. The downgrade required by V2 below MUST happen INSIDE
the per-worktree compose stack's DB, NOT against the live orch DB.
Confirm by checking `$IW_BROWSER_BASE_URL` is NOT `http://localhost:9900`
(the live dashboard) — it must be the per-worktree stack URL.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built
from THIS worktree's source code. The environment is ready before this
prompt runs — do NOT attempt to start, stop, or rebuild any services.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Do NOT run `make dev`, `make e2e-up`,
`docker compose`, `playwright install`, or `agent-browser`. Use
`playwright-cli` exclusively.

## Input Files

- `ai-dev/active/I-00040/I-00040_Issue_Design.md`
- `dashboard/templates/base.html` (banner)
- `dashboard/templates/macros/db_guard.html` (write-action disable macro)
- `dashboard/app.py` (middleware + Jinja global)
- `orch/db/alembic_guard.py` (helper)

## Output Files

- `ai-dev/active/I-00040/reports/I-00040_S13_BrowserVerification_Report.md`
- `ai-dev/active/I-00040/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If a login is required (the dashboard may not require login in this
project — check `$IW_BROWSER_E2E_USER` is set first):

```bash
playwright-cli snapshot
# If a login form is present:
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:
1. Always `playwright-cli snapshot` before `fill` / `click`.
2. Wait for transitions before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00040/evidences/post/`.

## E2E DB seed data

The E2E stack starts with a fresh PostgreSQL with the project's schema
and migrations applied. The CR-00022/I-00040 verification does NOT
require historical step_runs/fix_cycles, so no `e2e_fixtures` file is
needed.

## Verification Steps

### V1: Banner is ABSENT when DB is at head

1. Navigate to `{{IW_BROWSER_BASE_URL}}/`.
2. **Verify:** the page renders normally; no element with
   `role="alert"` is present in the DOM; no element containing the
   string `Orch DB schema is behind head` exists.
3. **Verify:** at least one write-action button (e.g.
   `Approve batch`, `Launch item`, or `Approve item` — find one via
   `playwright-cli snapshot` on a relevant page) does NOT have the
   `disabled` attribute.
4. **Screenshot:** `ai-dev/active/I-00040/evidences/post/I-00040_v1_banner_absent.png`.

### V2: Banner APPEARS after downgrading the per-worktree DB by one revision

The per-worktree compose stack's DB host/port is exposed in the
worktree's `.env` as `IW_CORE_DB_HOST` / `IW_CORE_DB_PORT`. Apply a
one-revision downgrade against THAT DB only — never the live orch DB.

```bash
# Downgrade the per-worktree DB by one revision.
# IW_CORE_DB_* in this shell already points at the per-worktree DB
# (set up by the daemon's worktree_compose.up()).
uv run alembic downgrade -1
```

Then trigger the dashboard middleware to re-check (the throttle is 10s;
wait or hit any URL twice):

```bash
sleep 12
playwright-cli open "{{IW_BROWSER_BASE_URL}}/"
playwright-cli snapshot
```

1. **Verify:** an element with `role="alert"` is present.
2. **Verify:** that element contains the literal string
   `Orch DB schema is behind head`.
3. **Verify:** that element contains the literal string
   `make db-migrate`.
4. **Verify:** that element contains the head revision identifier (read
   it via `uv run alembic heads` in the same shell, or read
   `app.state.alembic_guard_status` if exposed via a debug endpoint).
5. **Screenshot:** `ai-dev/active/I-00040/evidences/post/I-00040_v2_banner_present.png`.

### V3: Write-action buttons are DISABLED when banner is shown

While the DB is still downgraded:

1. Navigate to a page that has a write-action button (e.g.
   `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/queue` for an
   `Approve item` button, or `/batches` for `Approve batch`).
2. `playwright-cli snapshot` and find the write-action button.
3. **Verify:** the button has `disabled` (HTML attribute) AND
   `aria-disabled="true"`.
4. **Verify:** the button's `title` attribute contains
   `make db-migrate`.
5. **Screenshot:** `ai-dev/active/I-00040/evidences/post/I-00040_v3_buttons_disabled.png`.

### V4: A state-mutating endpoint returns HTTP 503

While the DB is still downgraded:

```bash
# Use curl (NOT playwright-cli — this is an API check, not a UI check).
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "{{IW_BROWSER_BASE_URL}}/batches/BATCH-00099/approve"
```

1. **Verify:** HTTP status is `503`.
2. **Verify:** response body contains `make db-migrate`.

(Use any plausible batch ID — the route should return 503 from the
guard BEFORE looking up the BatchItem, so a non-existent ID is fine.)

### V5: Restoring the DB clears the banner

```bash
uv run alembic upgrade head
sleep 12
playwright-cli open "{{IW_BROWSER_BASE_URL}}/"
playwright-cli snapshot
```

1. **Verify:** no element with `role="alert"` remains.
2. **Verify:** previously-disabled write-action buttons are now enabled
   (no `disabled` attribute).
3. **Screenshot:** `ai-dev/active/I-00040/evidences/post/I-00040_v5_banner_cleared.png`.

### V6: No Regressions

1. Revisit the dashboard's Queue, History, Batches, Jobs, Worktrees,
   and Code pages. Each must render with HTTP 200 and no console
   errors (in either banner-present or banner-absent state).
2. **Verify:** no new console errors observed during V1..V5.
3. **Screenshot:** `ai-dev/active/I-00040/evidences/post/I-00040_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. Any failure requires `iw step-fail` with a
specific reason. Classify failures:

- **CODE DEFECT** — wrong DOM, wrong HTTP code, wrong copy. Normal
  `--reason`.
- **ENV_DATA_MISSING** — page renders but lacks the data the
  verification expects. Prefix `--reason` with `ENV_DATA_MISSING:`
  (this issue is unlikely to hit this class).

## Report

Write `ai-dev/active/I-00040/reports/I-00040_S13_BrowserVerification_Report.md`:

- Pass/fail table for V1..V6.
- The concrete `$IW_BROWSER_BASE_URL` used.
- Any issues found with `file:line` references.
- List of screenshots captured.
- "No regressions observed" subsection.

Then call:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00040/reports/I-00040_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00040/reports/I-00040_S13_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00040",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "Banner absent at head", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Banner present after downgrade", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Write buttons disabled", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Mutating endpoint returns 503", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Restoring DB clears banner", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
