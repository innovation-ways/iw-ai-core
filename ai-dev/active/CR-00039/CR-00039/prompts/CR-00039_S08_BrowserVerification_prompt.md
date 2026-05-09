# Browser Verification Prompt: CR-00039-S08-BrowserVerification

**Work Item**: CR-00039 — Step Pipeline: Labeled Pill Redesign with Fix-Cycle Expansion
**Step**: S08
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
  1. Testcontainers spun up by pytest fixtures (they self-label and self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which commands are safe.

## ⛔ Migrations: agents generate, daemon applies

This CR makes no database changes. Do not touch migrations.

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS
worktree's source code. The environment is ready before this prompt runs.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Do NOT run `make dev`, `make e2e-up`, or any docker compose command.
Use `playwright-cli` exclusively — not `agent-browser`, not direct `chromium.launch()`.

---

## Input Files

- `ai-dev/active/CR-00039/CR-00039_CR_Design.md`
- `dashboard/templates/components/step_pipeline.html`
- `dashboard/templates/fragments/item_overview.html`
- `dashboard/static/styles.css`

## Output Files

- `ai-dev/active/CR-00039/reports/CR-00039_S08_BrowserVerification_Report.md`
- `ai-dev/active/CR-00039/evidences/post/` — screenshots taken during verification

---

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
playwright-cli snapshot   # get login form refs
playwright-cli fill <user-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <pass-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-ref>
```

---

## E2E DB seed data

The E2E stack is seeded from production. It will contain real work items including items
that had fix cycles. Use an existing item that has `fix_cycle_count > 0` on at least one
step — look for items with "FIX CYCLES" badge > 0 on the dashboard, or navigate to the
History page of the `iw-ai-core` project and pick a completed item with fix cycles.

If no item with fix cycles is visible (empty-state scenario), use any completed item for
V1–V2 and note the ENV_DATA_MISSING for V3.

---

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify)

### V1: Step IDs are visible in the pipeline strip

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/history` and open any completed
   item (click its ID link to reach the item detail page).
2. Locate the "Step Pipeline" section on the Overview tab.
3. **Verify:** the pipeline strip contains pill-shaped blocks (visually taller and wider
   than tiny squares), each showing a step label (`S00`, `S01`, `S02`, …) as readable text.
   Assert that the text "S00" or "S01" is present on the page within the pipeline section.
4. **Screenshot:** `playwright-cli screenshot` then
   `cp .playwright-cli/page-*.png ai-dev/active/CR-00039/evidences/post/CR-00039_v1_step_ids_visible.png`

### V2: Duration appears inside the pill — no separate misaligned row

1. On the same item detail page from V1.
2. **Verify:** each completed step pill shows a duration value (e.g. "7m44s" or "11m26s")
   as a second line inside the pill. Confirm that a duration row with `flex items-center gap-1 mt-2`
   does NOT appear below the strip (inspect the DOM snapshot — it must be absent).
3. **Screenshot:** `ai-dev/active/CR-00039/evidences/post/CR-00039_v2_duration_inline.png`

### V3: Fix-cycle reruns show as separate amber ↺SXX pills

1. Navigate to a completed item that had at least one fix cycle (FIX CYCLES > 0).
   If the item from V1 qualifies, stay on that page. Otherwise navigate to another item.
2. **Verify:** at least one step in the strip shows an amber-coloured pill labelled with
   `↺` followed by the step ID (e.g. `↺S03`). The amber pill must appear immediately
   after the original step's pill.
3. **Screenshot:** `ai-dev/active/CR-00039/evidences/post/CR-00039_v3_fixcycle_pills.png`

If no item with fix cycles is available in the E2E DB, report `ENV_DATA_MISSING` per the
Pass Criteria instructions — do not attempt to fabricate fix cycle data.

### V4: Step table below the pipeline is intact

1. On the same item detail page.
2. Scroll down past the pipeline strip to the step detail table.
3. **Verify:** the table renders all steps with Step, Agent, CLI, Model, Status, Started,
   Duration, Runs, and Error columns. Status badges are coloured correctly. The table is
   not broken or missing.
4. **Screenshot:** `ai-dev/active/CR-00039/evidences/post/CR-00039_v4_step_table_intact.png`

### V5: No Regressions

1. Navigate to at least one other item detail page (a different item).
2. Verify the pipeline strip renders there as well (no blank section or JS error).
3. Navigate to the batch detail page and verify the pipeline strip used in batch_detail.html
   (if present) still renders without error.
4. Verify no new console errors appeared on any page visited during V1–V4.
5. **Screenshot:** `ai-dev/active/CR-00039/evidences/post/CR-00039_v5_no_regressions.png`

---

## Pass Criteria

All V1–V5 must pass. Failures → `iw step-fail`. Classify per code_defect / env_data_missing / spec_mismatch.

```bash
# Pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00039/reports/CR-00039_S08_BrowserVerification_Report.md

# Fail
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<reason>" \
  --report ai-dev/active/CR-00039/reports/CR-00039_S08_BrowserVerification_Report.md
```

---

## Report

Write `ai-dev/active/CR-00039/reports/CR-00039_S08_BrowserVerification_Report.md` with:
- Pass/fail table for V1–V5
- The exact `$IW_BROWSER_BASE_URL` used
- Screenshots captured (relative paths)
- No regressions subsection

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "qv-browser",
  "work_item": "CR-00039",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Step IDs visible", "status": "pass|fail", "failure_class": null, "screenshot": "CR-00039_v1_step_ids_visible.png", "notes": ""},
    {"id": "V2", "name": "Duration inline no separate row", "status": "pass|fail", "failure_class": null, "screenshot": "CR-00039_v2_duration_inline.png", "notes": ""},
    {"id": "V3", "name": "Fix-cycle amber pills", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "CR-00039_v3_fixcycle_pills.png", "notes": ""},
    {"id": "V4", "name": "Step table intact", "status": "pass|fail", "failure_class": null, "screenshot": "CR-00039_v4_step_table_intact.png", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "failure_class": null, "screenshot": "CR-00039_v5_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
