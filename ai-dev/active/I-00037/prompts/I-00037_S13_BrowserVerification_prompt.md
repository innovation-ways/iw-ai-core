# Browser Verification Prompt: I-00037-S13-BrowserVerification

**Work Item**: I-00037 -- Per-project dashboard still uses item-level batch progress after I-00036
**Step**: S13
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state. The isolated E2E stack is managed by the orchestrator — do NOT attempt
to start, stop, or rebuild it.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations expected.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from
THIS worktree's source code. The environment is ready before this prompt
runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, no
`localhost:3100`). Always use `$IW_BROWSER_BASE_URL`. The port is allocated
per-worktree so concurrent browser_verification steps don't collide.

Do NOT run any of the following — they will break the isolated stack or
duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser` — this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet — always go through
  `playwright-cli`

## Input Files

- `ai-dev/active/I-00037/I-00037_Issue_Design.md` -- Design document
- `ai-dev/active/I-00037/evidences/pre/I-00037-dashboard-home-shows-0pct.png` -- Pre-fix: dashboard home @ 0%
- `ai-dev/active/I-00037/evidences/pre/I-00037-batches-view-shows-correct-pct.png` -- Pre-fix: batches view @ 94%
- `dashboard/utils/batch_progress.py` -- Shared helper (S01)
- `dashboard/routers/project_dashboard.py` -- Rewired home (S03)
- `dashboard/routers/batches.py` -- Rewired batches (S03)
- All files listed in the S01, S03 reports' `files_changed`

## Output Files

- `ai-dev/active/I-00037/reports/I-00037_S13_BrowserVerification_Report.md` -- Mandatory report
- `ai-dev/active/I-00037/evidences/post/` -- Post-fix screenshots

## Prerequisites

Every run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in using accessible refs from the snapshot:

```bash
playwright-cli snapshot                       # get refs (e10, e12, ...)
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill`/`click` to read
   current accessible element IDs. Do not guess selectors or reuse refs
   from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00037/evidences/post/` with
   descriptive filenames.

## E2E DB seed data — fixture required

The baseline seed (`scripts/e2e_seed.py`) does NOT create a batch in the
partial-step-completion state this verification needs. Add a fixture file
**before running your verifications**:

```
ai-dev/active/I-00037/e2e_fixtures/001_partial_progress_batch.py
```

The fixture must export `def seed(db: Session) -> None` and must:

- Be **idempotent** — `db.get(...)` / `db.scalar(select(...))` guard every
  insert. `e2e_up.sh` may re-run on retry.
- Create one work item (e.g., `I-TEST-37`) with **10 `WorkflowStep` rows**.
  Steps 1..3 → `StepStatus.completed`; steps 4..10 → `StepStatus.pending`.
- Create one batch (e.g., `BATCH-TEST37`) with `BatchStatus.executing` and
  one `BatchItem` linking to the work item with
  `BatchItemStatus.in_progress`.
- Use the same `project_id` the central seed uses (inspect
  `scripts/e2e_seed.py`).

The dashboard container bind-mounts `ai-dev/` read-only, so writing the
fixture file is enough — the next `scripts/e2e_seed.py` invocation picks it
up. If the stack was already provisioned before the fixture was added, call
`iw step-fail` with `ENV_DATA_MISSING:` to ask the daemon to re-provision.

## Verification Steps

### V1: Primary — dashboard home shows step-based progress (~30%)

1. Navigate to `$IW_BROWSER_BASE_URL/project/<project_id>/` (replace
   `<project_id>` with the central-seed project id — read it from the seed
   script).
2. Wait for the Active Batches card to render.
3. **Verify:**
   - The card for `BATCH-TEST37` (or whatever ID the fixture used) shows
     `0/1 items` in the items label (unchanged — item-level per the user's
     explicit instruction).
   - The "% complete" label shows **30%** (±1% rounding tolerance) — NOT 0%
     (the pre-fix value) and NOT 100%.
   - The progress bar is visibly filled to ~30% of its width.
4. **Screenshot:** `playwright-cli screenshot --filename ai-dev/active/I-00037/evidences/post/I-00037_v1_home_30pct.png --full-page`

### V2: Batches view shows the same step-based progress

1. Navigate to `$IW_BROWSER_BASE_URL/project/<project_id>/batches`.
2. **Verify:**
   - The row for `BATCH-TEST37` shows **30%** in the Progress column
     (matching V1 exactly — ±1% tolerance).
   - The Items column shows `0/1`.
3. **Screenshot:** `ai-dev/active/I-00037/evidences/post/I-00037_v2_batches_30pct.png`

### V3: Parity — the two views AGREE on the same batch

This is the key verification that distinguishes I-00037 from a partial fix.

1. Compare the percentage read in V1 (dashboard home) to the percentage read
   in V2 (batches view) for `BATCH-TEST37`.
2. **Verify:** they are identical (or within ±1% rounding). A difference ≥ 2%
   means the fix did not consolidate the source of truth — treat it as a
   CODE DEFECT.
3. **Screenshot:** a split comparison or note the two values in the report
   explicitly (no new screenshot required — V1 and V2 captures suffice).

### V4: No Regressions

1. Navigate to `$IW_BROWSER_BASE_URL/project/<project_id>/batch/BATCH-TEST37`
   — the batch detail page. Verify it still renders cleanly (no 500, no
   template error).
2. Navigate to `$IW_BROWSER_BASE_URL/project/<project_id>/queue` and
   `$IW_BROWSER_BASE_URL/project/<project_id>/history` — confirm both render.
3. Check the browser console across all pages visited — **no new JS errors**.
4. **Screenshot:** `ai-dev/active/I-00037/evidences/post/I-00037_v4_no_regressions.png`

## Pass Criteria

All of V1..V4 must pass. Any failure (including partial or ambiguous) → call
`iw step-fail` with a specific reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — V1 shows 0% (item-based bug still live) or 100%
  (wrong formula); V1 and V2 disagree by ≥ 2% (drift not eliminated); a 500
  error; a JS console exception; wrong element rendered. Use a normal
  `--reason`.
- **ENV_DATA_MISSING** — the pages render cleanly with HTTP 200 but the
  seeded batch is missing (empty Active Batches list on the home, empty
  Batches table), OR the batch has no `WorkflowStep` rows (percentage is 0
  because there are truly 0 steps, not because the fix is broken). The
  fix-cycle agent **cannot** fix this by editing code — it needs an updated
  `e2e_fixtures` file. Prefix the reason with `ENV_DATA_MISSING:`:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: seeded BATCH-TEST37 not visible on /project/<id>/ — fixture ai-dev/active/I-00037/e2e_fixtures/001_partial_progress_batch.py missing or not loaded" \
    --report ai-dev/active/I-00037/reports/I-00037_S13_BrowserVerification_Report.md
  ```

## Report

Write `ai-dev/active/I-00037/reports/I-00037_S13_BrowserVerification_Report.md`
containing:

- Pass/fail table, one row per V1..V4.
- The concrete `$IW_BROWSER_BASE_URL` used (copy from env so the report is
  self-contained).
- Any console errors observed on any page.
- A **Parity check** subsection explicitly listing the two percentages read
  (V1 vs V2) and confirming they match.
- Comparison against pre-fix evidence: reference both
  `evidences/pre/I-00037-dashboard-home-shows-0pct.png` (0% bug) and
  `evidences/pre/I-00037-batches-view-shows-correct-pct.png` (94% correct)
  and explain how the post-fix `evidences/post/` pair demonstrates the
  inconsistency is gone.
- List of all screenshots captured under `evidences/post/`.
- A **No regressions observed** subsection covering V4 (detail / queue /
  history / console).

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00037/reports/I-00037_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00037/reports/I-00037_S13_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the
orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00037",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "dashboard home shows 30%", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "batches view shows 30%", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "parity between home and batches view", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "no regressions (detail / queue / history / console)", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status: pass` iff every V(n) is `pass`.
- `base_url_used`: actual URL from `$IW_BROWSER_BASE_URL` — reviewers verify
  the worktree stack (not the live dashboard) was tested.
- V3 is the parity lock — the defining success criterion for this incident.
