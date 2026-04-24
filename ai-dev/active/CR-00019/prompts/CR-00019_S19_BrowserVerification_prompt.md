# Browser Verification Prompt: CR-00019-S19-BrowserVerification

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step**: S19
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

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:9900`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment.

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md` — the design document
- `dashboard/templates/pages/project/oss.html`
- Any new fragments under `dashboard/templates/fragments/oss_*.html`
- `dashboard/static/oss_tab.js` (if created in S09) or the inline script block
- `dashboard/routers/oss.py`
- `dashboard/services/oss_service.py`
- `dashboard/routers/worktrees.py`

## Output Files

- `ai-dev/active/CR-00019/reports/CR-00019_S19_BrowserVerification_Report.md`
- `ai-dev/active/CR-00019/evidences/post/` — all verification screenshots

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
3. Screenshots go under `ai-dev/active/CR-00019/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack starts with a fresh PostgreSQL. It has schema + migrations applied, plus the baseline seed (project row, architecture map, three demo work items).

**This CR needs OSS data** that the baseline seed does not provide: at minimum, a project row with `oss_enabled=true`, a completed `OssScan` with a red pill, and several `OssFinding` rows covering pass / fail+auto_fix_true / fail+auto_fix_false / human_required / skip / MUST+SHOULD+INFO. Create a fixture:

```
ai-dev/active/CR-00019/e2e_fixtures/001_oss_demo_scan.py
```

The file must export `def seed(db: Session) -> None` and be idempotent (check `db.get(...)` before insert). It should create:

1. A Project row (or reuse the demo project) with `oss_enabled=True`.
2. One `OssScan` with `pill_color="red"`, `completed_at=now - 5 minutes` (fresh, not stale).
3. At least 8 `OssFinding` rows spanning:
   - A MUST fail with `auto_fix_available=True` and a non-empty rationale (e.g. OSS-LIC-01 "LICENSE file missing").
   - A MUST fail with `auto_fix_available=False`.
   - A SHOULD fail with `auto_fix_available=True` (e.g. OSS-LIC-06 "NOTICE file missing").
   - A human_required with `auto_fix_available=True`.
   - A pass.
   - A skip.
   - Each with `osps_control` set to a realistic code (e.g. "OSPS-LE-03.01").

If any verification requires an **awaiting-review job**, create a corresponding `ProjectOssJob` row in `awaiting_review` state with `base_sha`, `branch_name="iw-oss-publish/prep-42"`, `commit_sha`, and `files_changed_summary` populated. The worktree on disk is out of scope for this fixture — the browser test verifies UI rendering, not the git state.

The fixture auto-runs after `scripts/e2e_seed.py`. Multiple files load in lexical order — use `001_`, `002_` prefixes if you split.

> ⚠️ **NEVER run the fixture seed from your host shell.** Exec into the E2E dashboard container if you need to re-seed a running stack. If the fixture needs to be re-seeded against a running E2E stack, call `iw step-fail` with `ENV_DATA_MISSING:` prefix — the daemon re-provisions.

## Verification Steps

Replace the V1..V(n) below with concrete per-AC verifications. Each V must state: what to navigate to, what to click/type, what to verify, and capture a screenshot.

### V1: New table layout is the primary view (AC1, AC2, AC3)

1. Navigate to `$IW_BROWSER_BASE_URL/project/<demo-project-id>/oss`.
2. Take a `playwright-cli snapshot` and verify:
   - There is NO button labeled "Prepare" in the top action row (only Scan + Publish).
   - There is NO anchor containing text "Fix via Prepare" anywhere.
   - There is a table grouped by domain with per-row checkboxes.
   - There is a filter chip row with "All" / "Failing only" / "MUST only" — "Failing only" is the active one (aria-pressed="true").
   - By default, only failing rows are visible (pass rows are hidden).
3. **Verify**: three filter chips present, default = Failing only; no dead links.
4. **Screenshot**: `ai-dev/active/CR-00019/evidences/post/CR-00019_v1_table_default_view.png`.

### V2: Checkbox enablement rule (AC2)

1. Snapshot the table.
2. Verify by inspecting the snapshot:
   - The row for the MUST fail with `auto_fix_available=true` has an enabled checkbox.
   - The row for the MUST fail with `auto_fix_available=false` has a disabled checkbox + tooltip "Manual action — see details".
   - Pass rows (when filter chip is set to All) render no checkbox.
3. **Verify**: checkbox presence/enablement matches the rule.
4. **Screenshot**: `ai-dev/active/CR-00019/evidences/post/CR-00019_v2_checkbox_rule.png` with the filter set to "All" so all rules are visible.

### V3: Filter chips (AC3)

1. Click the "All" chip.
2. Verify the table now shows pass + fail + skip rows.
3. Click the "MUST only" chip.
4. Verify only MUST rows are visible (no SHOULD, no INFO).
5. Click "Failing only" to return to default.
6. **Screenshot**: `ai-dev/active/CR-00019/evidences/post/CR-00019_v3_filter_must_only.png`.

### V4: Details modal with rationale + OSPS link (AC4, AC13)

1. Click the `…` (Details) button on the OSS-LIC-01 row.
2. Verify the modal opens with:
   - Heading includes "OSS-LIC-01".
   - A "Why this matters" section with the rationale paragraph.
   - A "Remediation" section.
   - An external link whose href is exactly `https://baseline.openssf.org/#OSPS-LE-03.01` (or whatever osps_control the fixture used) with `target="_blank"`.
3. Press Escape — modal closes.
4. **Screenshot**: `ai-dev/active/CR-00019/evidences/post/CR-00019_v4_details_modal.png` (with modal open).

### V5: Selection + confirm dialog + Prepare fix (AC5)

1. Tick two enabled checkboxes (e.g. OSS-LIC-01 and OSS-LIC-06).
2. Verify the Prepare button now reads "Prepare fix (2 selected)" and is enabled.
3. Click the button.
4. Verify a confirm dialog appears listing both check IDs with their summaries.
5. Click Cancel; verify nothing fires (no progress spinner, no SSE).
6. Re-tick if needed, click the button again, click Confirm.
7. Verify the progress block appears (existing SSE UI) — a live subprocess may not complete within the verification window, which is fine. What matters is the POST fired (check network via snapshot, or verify a new `ProjectOssJob` row exists with kind=prepare and status ∈ {queued, running}).
8. **Screenshot**: `ai-dev/active/CR-00019/evidences/post/CR-00019_v5_confirm_dialog.png`.

### V6: Awaiting-review card + Accept flow (AC7, AC8)

Preconditions: the fixture has seeded an `awaiting_review` job. The E2E environment does NOT have a real worktree for that job — so the Accept click will fail at the git step. That's acceptable for this verification: we're checking the UI renders correctly and fires the POST, not the git side-effect.

1. Navigate to the OSS tab.
2. Verify the awaiting-review card is visible above the Scan/Publish row, showing: worktree path, branch, files-changed summary, "Waiting N days" age, Accept and Discard buttons.
3. Click "Accept fix".
4. Expected: the POST fires and receives a 500 (git ops fail because no real worktree). The UI shows the server error message. Verify the error message is surfaced to the user (not a silent failure).
5. Verify the job row in the DB moved to `error` or stayed in `awaiting_review` per S07's error-recovery rules.
6. **Screenshot**: `ai-dev/active/CR-00019/evidences/post/CR-00019_v6_awaiting_review_card.png`.

If this verification's preconditions can't be met because the fixture wasn't created, call `iw step-fail` with `ENV_DATA_MISSING:` prefix.

### V7: Discard flow (AC10)

1. Reload the OSS tab (the fixture's awaiting-review job should still be present unless V6 moved it to `error`).
2. Click Discard on the awaiting-review card.
3. A confirm dialog appears — verify the copy matches "Discard the auto-fix for job #N? The worktree and branch will be deleted."
4. Click Confirm.
5. Verify the POST fires. Because no real worktree/branch exists, the idempotent path triggers (log warn, still returns 200). Verify the job row moves to `discarded`.
6. Page reloads; awaiting-review card is gone.
7. **Screenshot**: `ai-dev/active/CR-00019/evidences/post/CR-00019_v7_discard.png`.

### V8: Stale scan disables Prepare button (AC12)

Preconditions: a second fixture (`ai-dev/active/CR-00019/e2e_fixtures/002_stale_scan.py`) that overrides `scan_summary.is_stale` to true, or a second demo project whose scan is older than the freshness threshold.

1. Navigate to the stale project's OSS tab.
2. Tick an enabled checkbox.
3. Verify the Prepare button is **disabled** even though selection ≥ 1.
4. Verify a "Re-scan first" banner / tooltip is visible.
5. **Screenshot**: `ai-dev/active/CR-00019/evidences/post/CR-00019_v8_stale_scan.png`.

### V9: /system/worktrees surfaces OSS-prep worktrees (AC14)

1. Navigate to `$IW_BROWSER_BASE_URL/system/worktrees`.
2. Verify the table includes a row with path containing `.worktrees/oss-prep-` and a distinct "OSS prep" badge (fixture's awaiting-review job provides the row, even if no on-disk worktree exists — the row should appear based on DB state, not on-disk scan; flag as CODE DEFECT if the current implementation only scans disk and misses the fixture's record).
3. **Screenshot**: `ai-dev/active/CR-00019/evidences/post/CR-00019_v9_worktrees_page.png`.

### V10: No Regressions

1. Navigate to `$IW_BROWSER_BASE_URL/project/<demo-project-id>/jobs` — page renders, no errors.
2. Navigate to `$IW_BROWSER_BASE_URL/project/<demo-project-id>/tests` — page renders, no errors.
3. Return to `/oss` — click Scan button. Verify the scan progress UI still works (the original flow).
4. Verify NO new console errors appeared on any page visited during V1..V9.
5. **Screenshot**: `ai-dev/active/CR-00019/evidences/post/CR-00019_v10_no_regressions.png`.

## Pass Criteria

All V1..V10 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

### Distinguishing code defects from environment gaps

Before failing the step, classify the failure:

- **CODE DEFECT** — the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** — the page rendered cleanly but the fixtures this verification expects weren't seeded (e.g. the awaiting-review row is missing, or no OSS findings exist). Prefix the reason with `ENV_DATA_MISSING:`:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V6 expects ProjectOssJob in awaiting_review — add ai-dev/active/CR-00019/e2e_fixtures/001_oss_demo_scan.py" \
    --report ai-dev/active/CR-00019/reports/CR-00019_S19_BrowserVerification_Report.md
  ```

## Report

After verification, write `ai-dev/active/CR-00019/reports/CR-00019_S19_BrowserVerification_Report.md` containing:

- Pass/fail table with one row per V1..V10.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with file:line references if root cause was investigated.
- List of screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00019/reports/CR-00019_S19_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00019/reports/CR-00019_S19_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S19",
  "agent": "qv-browser",
  "work_item": "CR-00019",
  "overall_status": "pass|fail",
  "base_url_used": "<actual URL from $IW_BROWSER_BASE_URL>",
  "verifications": [
    {"id": "V1", "name": "New table layout", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Checkbox rule", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Filter chips", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Details modal", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Selection + confirm", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Awaiting-review + Accept", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "Discard", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V8", "name": "Stale disables", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V9", "name": "Worktrees page", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V10", "name": "No regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed.
- `base_url_used`: the concrete URL actually hit.
- `console_errors_observed`: any console errors during any V(n), even if the verification otherwise passed.
