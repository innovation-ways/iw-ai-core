# Browser Verification Prompt: I-00058-S13-BrowserVerification

**Work Item**: I-00058 — DocGenerationJob IDs are UUIDs instead of sequential DOC-NNNNN identifiers
**Step**: S13
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Allowed exceptions: testcontainers (pytest), read-only introspection, `./ai-core.sh` / `make` targets.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:3100`). Always use the env var.

Do NOT run `make dev`, `make e2e-up`, `docker compose`, `playwright install`, `agent-browser`, or any `chromium.launch()` snippet. Use `playwright-cli` **exclusively**.

## Input Files

- `ai-dev/active/I-00058/I-00058_Issue_Design.md` — Design document
- `orch/db/models.py` — `DocGenerationJob` model with `public_id` column and listener
- `orch/jobs/aggregator.py` — updated `_fetch_doc_generation` and `_get_doc_generation`

## Output Files

- `ai-dev/active/I-00058/reports/I-00058_S13_BrowserVerification_Report.md` — mandatory report
- `ai-dev/active/I-00058/evidences/post/` — screenshots taken during verification

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

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00058/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB via `pg_dump`. If no `doc_generation_jobs` rows exist in the seeded DB, the Jobs table may show an empty state — classify this as `ENV_DATA_MISSING` (see Pass Criteria), not a code defect.

If you need to seed a doc generation job row for verification, add a fixture:

```
ai-dev/active/I-00058/e2e_fixtures/001_doc_generation_job.py
```

Export `def seed(db: Session) -> None` that inserts one `DocGenerationJob` row with a `public_id` like `"DOC-00001"`. Make it idempotent (check before insert). Then re-run the seed inside the app container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

## Verification Steps

### V1: Jobs table shows DOC-NNNNN for doc generation jobs (primary AC)

1. Navigate to `$IW_BROWSER_BASE_URL` and log in.
2. Navigate to the Jobs page for any project (e.g., `$IW_BROWSER_BASE_URL/<project-slug>/jobs`).
3. Filter or scroll to find a `doc_generation` type row (look for rows labelled "Doc generation" or similar).
4. **Verify:** The Job ID column for that row displays `DOC-NNNNN` format (e.g., `DOC-00001`), NOT a UUID string (like `2fb5a9a9-4b2d-...`).
5. **Screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00058/evidences/post/I-00058_v1_jobs_table_doc_id.png`.

### V2: No UUID visible for doc generation rows

1. Still on the Jobs page.
2. Inspect all visible `doc_generation` rows.
3. **Verify:** No UUID-format string (matching `[0-9a-f]{8}-[0-9a-f]{4}-`) is visible in the Job ID column for any doc generation row.
4. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00058/evidences/post/I-00058_v2_no_uuids.png`.

### V3: No Regressions

1. Navigate to adjacent pages: Batches, Tests, and Code Index jobs pages.
2. Verify those job types still show their correct IDs (`BATCH-NNNNN`, `CM-NNNNN`, etc.).
3. Verify no new console errors appeared on any page visited during V1–V2.
4. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00058/evidences/post/I-00058_v3_no_regressions.png`.

## Pass Criteria

All V1..V3 must pass. Any failure — including partial or ambiguous result — requires calling `iw step-fail`.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — Jobs table shows a UUID string instead of DOC-NNNNN, or throws an error. Use a normal `--reason`.
- **ENV_DATA_MISSING** — Jobs table renders cleanly with HTTP 200 but shows "No jobs" because the E2E DB has no `doc_generation_jobs` rows. Prefix reason with `ENV_DATA_MISSING:` and add a seed fixture.

## Report

After verification, write `ai-dev/active/I-00058/reports/I-00058_S13_BrowserVerification_Report.md` containing:

- Pass/fail table with one row per V1..V3.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found with `file:line` references.
- List of screenshots captured.
- **No regressions observed** subsection.

Then call one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00058/reports/I-00058_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00058/reports/I-00058_S13_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00058",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "Jobs table shows DOC-NNNNN", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "No UUID visible for doc generation rows", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "No regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
