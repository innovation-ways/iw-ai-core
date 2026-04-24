# Browser Verification Prompt: CR-00020-S15-BrowserVerification

**Work Item**: CR-00020 -- Store work item evidences as BLOBs in the database
**Step**: S15
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

Your job is to verify behaviour in the browser. The migration from S01 has
already been applied to the isolated E2E stack by the daemon before this
step runs. Do not run migrations yourself.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, no `localhost:5173`, no other literal). Always use `$IW_BROWSER_BASE_URL`.

Do NOT run any of the following -- they will break the isolated stack:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser` or direct `chromium.launch()` calls

Use `playwright-cli` **exclusively**.

## Input Files

- `ai-dev/active/CR-00020/CR-00020_CR_Design.md` -- the design document
- `ai-dev/active/CR-00020/evidences/pre/CR-00020-before-empty-evidences-tab.png` -- baseline: the broken Evidences tab on archived I-00036
- Files listed in the S01/S03/S05 reports' `files_changed`

## Output Files

- `ai-dev/active/CR-00020/reports/CR-00020_S15_BrowserVerification_Report.md` -- mandatory report
- `ai-dev/active/CR-00020/evidences/post/` -- post-fix screenshots

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot                       # get accessible element refs
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:

1. Always `playwright-cli snapshot` **before** `fill` / `click`. Do not reuse refs from a prior page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00020/evidences/post/` with descriptive filenames.

## E2E DB seed data — fixture required

The baseline seed (`scripts/e2e_seed.py`) has one project plus three demo work items but does NOT create a work_item with pre-seeded evidence rows in the new `work_item_evidences` table. This verification needs both kinds of evidence.

Add a fixture file **before running verifications**:

```
ai-dev/active/CR-00020/e2e_fixtures/001_evidence_item.py
```

The fixture must export `def seed(db: Session) -> None` and must:

- Be **idempotent** — `db.get(...)` / `db.scalar(select(...))` before insert; `e2e_up.sh` may re-run on retry.
- Create one work_item `CR-00020-E2E` in status `completed` (or any status — we only query evidences), project_id matching `scripts/e2e_seed.py`.
- Insert **two** `WorkItemEvidence` rows:
  - `(project, 'CR-00020-E2E', 'pre', 'baseline.png', 'image/png', <N> bytes of deterministic PNG content, step_id=NULL)`
  - `(project, 'CR-00020-E2E', 'post', 'fixed.png', 'image/png', <N> bytes of deterministic PNG content, step_id='S11')`

Use the smallest valid PNG you can craft (e.g. a 1×1 transparent PNG: the 67-byte well-known minimal PNG) so the content is recognizable when rendered.

Do NOT also create `ai-dev/active/CR-00020-E2E/evidences/` on disk in the container — we want the pure DB-only path exercised (AC5). The dashboard container bind-mounts `ai-dev/` read-only from the worktree; if you create FS files, the test no longer proves DB-only rendering.

If the stack was provisioned before you added the fixture, call `iw step-fail` with `ENV_DATA_MISSING:` so the daemon re-provisions.

## Verification Steps

### V1: DB-only item renders both phases

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/item/CR-00020-E2E`.
2. Click the `Evidences` tab.
3. **Verify:**
   - The page shows a `Pre-Fix` section with `baseline.png`.
   - The page shows a `Post-Fix` section with `fixed.png`.
   - No console errors.
   - The work item has NO `ai-dev/active/CR-00020-E2E/evidences/` directory in the worktree (confirm via `ls` inside a separate bash step; the dashboard must be rendering purely from DB).
4. **Screenshot:** `playwright-cli screenshot --filename ai-dev/active/CR-00020/evidences/post/CR-00020_v1_db_only_tab.png --full-page`.

### V2: Evidence image served from DB bytes

1. Navigate directly to the image URL for the pre-evidence:
   `$IW_BROWSER_BASE_URL/project/iw-ai-core/item/CR-00020-E2E/evidence/pre/baseline.png`.
2. **Verify:**
   - HTTP 200 response (check via `curl -I` in a separate bash step if the browser hides the status).
   - `Content-Type: image/png` response header (DB-row-derived, not mimetypes-guessed).
   - The browser displays the 1×1 pixel PNG (or whatever the fixture inserted).
3. **Screenshot:** `ai-dev/active/CR-00020/evidences/post/CR-00020_v2_image_from_db.png`.

### V3: Re-running approve is safe (AC3 idempotency in browser)

*Skip if not representable in the UI.* The idempotency AC is fully covered by integration tests in S07. If you want to spot-check in the browser, visit the item's Overview tab and confirm status/evidence counters are stable after a refresh.

Mark as **n/a** with a note pointing to `tests/integration/test_evidences_cli.py::test_reingest_upsert_updates_content_keeps_id` if you cannot easily re-trigger approval from the UI.

### V4: Pre-fix broken state still documented

1. Navigate to a pre-existing archived item (like `I-00036`) at `$IW_BROWSER_BASE_URL/project/iw-ai-core/item/I-00036`.
2. Click the `Evidences` tab.
3. **Verify:**
   - The tab renders without error (it will be empty — archived items don't have DB evidence rows because this CR is forward-only).
   - No console errors.
4. **Screenshot:** `ai-dev/active/CR-00020/evidences/post/CR-00020_v4_legacy_archived_still_empty.png`.

This confirms the "no backfill" scope — already-archived items stay empty, exactly as the design says.

### V5: No Regressions

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/` (project dashboard) — renders cleanly.
2. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/queue` — renders cleanly.
3. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/history` — renders cleanly.
4. Revisit `$IW_BROWSER_BASE_URL/project/iw-ai-core/item/CR-00020-E2E` and click through other tabs (Overview, Design Doc, Reports, Logs) — each renders without console errors.
5. **Screenshot:** `ai-dev/active/CR-00020/evidences/post/CR-00020_v5_no_regressions.png`.

## Pass Criteria

All V1, V2, V4, V5 pass. V3 may be `n/a` with explicit deferral note. Any `fail` or ambiguous result → call `iw step-fail`.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — the Evidences tab shows an error, the image URL returns 500, Content-Type is wrong, the template fails. Normal `--reason`.
- **ENV_DATA_MISSING** — the fixture's work_item or evidence rows aren't visible. Prefix reason with `ENV_DATA_MISSING:`:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: seeded CR-00020-E2E with 2 evidences not visible — fixture ai-dev/active/CR-00020/e2e_fixtures/001_evidence_item.py missing or not loaded" \
    --report ai-dev/active/CR-00020/reports/CR-00020_S15_BrowserVerification_Report.md
  ```

## Report

Write `ai-dev/active/CR-00020/reports/CR-00020_S15_BrowserVerification_Report.md` containing:

- Pass/fail table with rows V1..V5 (V3 may be `n/a`)
- The concrete `$IW_BROWSER_BASE_URL` used
- Any console errors observed
- Comparison note: reference `evidences/pre/CR-00020-before-empty-evidences-tab.png` (baseline showing the empty tab on an archived item) vs `evidences/post/CR-00020_v1_db_only_tab.png` (post-fix, DB-sourced rendering)
- List of screenshots captured under `evidences/post/`
- **No regressions observed** subsection

Then:

```bash
# Full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00020/reports/CR-00020_S15_BrowserVerification_Report.md

# Any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00020/reports/CR-00020_S15_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "CR-00020",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "DB-only item renders both phases", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Evidence image served from DB bytes", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Idempotent re-approve (optional)", "status": "pass|fail|n/a", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Legacy archived item remains empty", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status: pass` iff every V is `pass` or `n/a`.
- `base_url_used`: actual URL from `$IW_BROWSER_BASE_URL`.
