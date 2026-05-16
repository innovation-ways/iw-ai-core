# Browser Verification Prompt: I-00086-S14-BrowserVerification

**Work Item**: I-00086 -- Runtime override controls give no UI feedback
**Step**: S14
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainer fixtures (not relevant to this step), read-only `docker ps` / `docker inspect` / `docker logs`, `./ai-core.sh` and `make` targets, and `docker compose exec app` when re-running an e2e fixture seed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this work item.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready — do NOT attempt to start, stop, or rebuild any services.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`). Do NOT hardcode application route paths beyond what you discover by navigation. Use `playwright-cli` exclusively — no `agent-browser`, no direct `chromium.launch()`.

Do NOT run: `make dev`, `make e2e-up`, any `docker compose` command (except `docker compose exec app` for seed re-run), `playwright install`, `npx playwright install`.

## Input Files

- `ai-dev/active/I-00086/I-00086_Issue_Design.md` — design document
- `dashboard/routers/runtime_overrides.py` (modified by S01)
- `dashboard/templates/fragments/item_overview.html` (modified by S03)
- `dashboard/templates/fragments/item_steps_table.html` (new in S03)

## Output Files

- `ai-dev/active/I-00086/reports/I-00086_S14_BrowserVerification_Report.md` — mandatory report
- `ai-dev/active/I-00086/evidences/post/` — screenshots captured

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in if the dashboard requires it (the worktree stack may not — confirm by snapshotting the first page). If a login form is present:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:

1. Always call `playwright-cli snapshot` BEFORE `fill` / `click` — read fresh element refs.
2. Wait for navigation to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00086/evidences/post/` with descriptive names.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB via `pg_dump`. It reflects current production state. If you cannot find an item with **at least 2 editable steps** (status `pending` or `failed`) for any project after navigating the History or Queue pages, the seed lacks the data this verification needs. In that case, add a fixture file:

```
ai-dev/active/I-00086/e2e_fixtures/001_editable_steps.py
```

It must export `def seed(db: Session) -> None`, must be idempotent (`db.get(...)` before insert), and must create a work item with at least 2 pending steps + at least 2 enabled `agent_runtime_options` rows (or rely on existing ones).

After writing the fixture, re-run the seed inside the `app` container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

⚠️ **NEVER run the seed from your host shell.** The host's `.env` resolves to the production orchestration DB on port 5433 — running `uv run python scripts/e2e_seed.py` outside a container will write test rows into the real DB.

If `docker compose exec` fails, call `iw step-fail` with `ENV_DATA_MISSING:` reason.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

The agent will visit every distinct page route referenced in V1..V5 and check fragment-target ids resolve and no unhandled JS/HTMX errors fire. V0 failure does NOT skip V1..V5.

### V1: Navigate to an item-detail page with editable steps

1. Navigate to `$IW_BROWSER_BASE_URL` and find a project list / project home.
2. Click into a project and then into the **History** (or **Queue**) page. Pick any item with at least one row showing a step in status `pending` or `failed` — these are the editable steps. The simplest path: open the project home and click the item's row to reach `/project/{id}/item/{item}`.
3. **Verify**: the **Overview** tab is visible by default, the steps table is rendered, the per-step `<select>` controls are visible on at least one row, and the **"Apply to remaining steps:"** footer is visible at the bottom of the table.
4. **Screenshot**: `ai-dev/active/I-00086/evidences/post/I-00086_v1_item_detail_initial.png`

### V2: Per-step model dropdown updates the row + shows toast

1. From the Overview tab, accessibility-snapshot the page (`playwright-cli snapshot`) and find the per-step CLI `<select>` ref on the first editable row.
2. Note the **current** Model column value in that row (look at the cell IMMEDIATELY to the right of the CLI `<select>` — that is the read-only Model column).
3. Change the per-step `<select>` to a different option using `playwright-cli` (snapshot → identify option ref → click or `select`).
4. **Verify** within ~2 seconds:
   - A toast notification appears (success-styled — typically green). The toast text contains the literal string `Model updated`.
   - The Model column for THAT SAME ROW updates to display the label corresponding to the option just selected. No manual refresh was performed.
   - No new console errors appeared (`cat .playwright-cli/console-*.log` after the action).
5. **Screenshot**: `ai-dev/active/I-00086/evidences/post/I-00086_v2_per_step_updated.png` (take the screenshot AFTER the toast and updated cell are both visible — re-snapshot if the toast has already faded).

### V3: Bulk Apply updates every editable row + shows count toast

1. Still on the same item-detail page (or reload it cleanly so V2's modifications are visible).
2. In the **"Apply to remaining steps:"** selector at the bottom of the steps table, pick a non-default runtime option that is DIFFERENT from what you set in V2 (so the visual change is unambiguous).
3. Click the **Apply** button.
4. **Verify** within ~2 seconds:
   - A toast appears with text matching the pattern `Model updated for N step(s)` where N is the number of editable rows currently visible (rows whose status is `pending` or `failed`). The toast is success-styled.
   - **Every** editable row's Model column now reflects the option you just chose. Rows that were NOT editable (e.g. `done`, `in_progress`) are unchanged.
   - No new console errors.
5. **Screenshot**: `ai-dev/active/I-00086/evidences/post/I-00086_v3_bulk_apply_updated.png`

### V4: Bulk Apply with zero-eligible-steps shows info toast

This verification is optional and depends on the seed. If you can navigate to an item where ALL steps are in non-editable status (e.g. `done`, `in_progress`, or `merged`):

1. Navigate to that item's detail page.
2. Even though no editable rows exist, the **"Apply to remaining steps:"** footer is still shown.
3. Pick any option and click Apply.
4. **Verify**:
   - A toast appears with the literal text `No editable steps to update`. It is info or warning styled (NOT success, NOT error).
   - No row in the table changes.
   - No console errors.
5. **Screenshot**: `ai-dev/active/I-00086/evidences/post/I-00086_v4_bulk_zero_eligible.png`

If no such item exists in the E2E seed, mark V4 as `n/a` in the report with reason `"ENV_DATA_MISSING: no item in seed has zero editable steps with the bulk footer rendered"` and add a seed fixture if practical. Do NOT fail the step on V4 alone.

### V5: No Regressions

1. Revisit the buttons/flows adjacent to the changed area in the steps table:
   - Open and close the run-history expander for any step whose `run_count > 1` (look for the small badge indicating fix cycles). Confirm it still expands and renders runs.
   - If the item has a MERGE step in `awaiting_approval`, confirm the **Approve merge** button still renders (do NOT click it).
   - If the item has any step in `failed`, confirm the **Restart** and **Skip** buttons still render (do NOT click them).
2. Confirm no console errors have accumulated on any page visited during V1..V4.
3. **Screenshot**: `ai-dev/active/I-00086/evidences/post/I-00086_v5_no_regressions.png`

## Pass Criteria

All V1, V2, V3, V5 must pass. V4 may be `n/a` if the seed lacks the required data and a fixture is not practical. Any failure that isn't `n/a` requires `iw step-fail` with a classified reason.

### Distinguishing failure classes

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx, threw console exception, or toast does not appear at all after a successful PATCH | CODE_DEFECT | normal `--reason` |
| Page rendered cleanly but cannot find an item with editable steps | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` + add fixture |
| Page rendered cleanly, design says no toast should fire (e.g. on validation failure), V step asks the agent to verify a toast anyway | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V{N} ..."` |

Per the design's **Acceptance Criteria**, the toast strings are EXACT:
- V2 toast text contains `Model updated`.
- V3 toast text matches `Model updated for {N} step(s)` with `(s)` literal.
- V4 toast text is `No editable steps to update`.

A toast that says e.g. `"Model updated for 3 steps"` (missing `(s)`) or `"Model updated successfully"` (extra word) is a CODE_DEFECT — the API contract is specific. Report it.

## Report

Write `ai-dev/active/I-00086/reports/I-00086_S14_BrowserVerification_Report.md` containing:

- A pass/fail table for V0..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- File/line refs to anything investigated (e.g. `dashboard/routers/runtime_overrides.py:280` for the toast emit).
- The list of screenshots captured.
- A **No regressions observed** subsection covering V5.

Then call:

```bash
# On full pass (V4 may be n/a)
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00086/reports/I-00086_S14_BrowserVerification_Report.md

# On any non-n/a failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00086/reports/I-00086_S14_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "I-00086",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "<actual url>",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Navigate to item with editable steps", "status": "pass|fail", "failure_class": "code_defect|env_data_missing|null", "screenshot": "I-00086_v1_item_detail_initial.png", "notes": ""},
    {"id": "V2", "name": "Per-step dropdown updates row + toast", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "I-00086_v2_per_step_updated.png", "notes": ""},
    {"id": "V3", "name": "Bulk Apply updates rows + count toast", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "I-00086_v3_bulk_apply_updated.png", "notes": ""},
    {"id": "V4", "name": "Bulk Apply zero-eligible info toast", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|null", "screenshot": "I-00086_v4_bulk_zero_eligible.png", "notes": ""},
    {"id": "V5", "name": "No regressions in adjacent controls", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "I-00086_v5_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
