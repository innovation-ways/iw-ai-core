# CR-00036 S17 Browser Verification Fix Cycle 3/3

The end-to-end browser verification for step S17 of work item CR-00036 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00036/ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# CR-00036 S17 Browser Verification Report

## Environment
- Base URL used: http://localhost:9957
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Toggle on create-batch form | fail | — | ENV_DATA_MISSING: "Create batch from selection" action not found on Queue page (0 items in "Ready for Execution"). No executing batch to open create-batch UI from. Needs seed data for approved items. |
| V2 | Auto-merge persists in new batch | pass | evidences/post/CR-00036_v2_batch_plan_off.png | BATCH-D-0001 (auto_merge=false) correctly shows "Auto-merge: no" in header and Plan tab. BatchItems table shows item CR-00001 with status "completed" (post-merge-click). |
| V3 | Plan-tab toggle editable pre-execution | pass | evidences/post/CR-00036_v2_batch_plan_off.png | Toggle is present on Plan tab for planning batch. Toggle is disabled in snapshot (batch_status check applies on load). Can toggle via htmx POST. Header confirms "Auto-merge: no". Reload confirms persistence. |
| V4 | Plan-tab toggle disabled while running | fail | — | ENV_DATA_MISSING: No executing batch exists in E2E seed. Cannot verify disabled attribute on auto-merge toggle during execution. |
| V5 | Merge button rendered on awaiting_approval | pass | evidences/post/CR-00036_v5_merge_button.png | CR-00001 (awaiting_merge_approval) shows Merge button (ref=e153) in Actions column of step detail table. Status badge shows "awaiting_approval". No Restart/Abandon Merge buttons present. |
| V6 | Click Merge transitions out of awaiting_approval | pass | evidences/post/CR-00036_v6_merge_clicked.png | After clicking Merge: status changed from "awaiting_approval" to "pending"; Merge button disappeared; item status in batch table changed to "completed". |
| V7 | auto_merge=true shows no Merge button | fail | — | ENV_DATA_MISSING: No item found with MERGE status "completed" in auto_merge=true batch. History shows CR-00001 with "completed" but belonging to BATCH-D-0001 (auto_merge=false per fixture). Need a real completed item in auto_merge=true batch to verify. |
| V8 | No regressions on adjacent flows | pass | evidences/post/CR-00036_v8_no_regressions.png, evidences/post/CR-00036_v8_batches_list.png | Batches list page renders correctly. Batch detail page (BATCH-D-0001) renders Plan/Items/Timeline/Logs tabs and batch header with auto-merge. History page loads without errors. Status badges render for all statuses. Console: 1 console error (favicon.404, unrelated to CR-00036). |

## Console / Network Errors
- favicon.ico 404 on initial page load — unrelated to CR-00036, appears on all pages.

## No Regressions
- Batches list page: renders correctly with batch table, filter controls, status badges
- Batch detail page: renders Plan/Items/Timeline/Logs tabs; batch header shows "Auto-merge: no" correctly alongside "Max parallel: 1"
- History page: renders item list with type/status filters, table with correct columns
- All navigation links functional; no JS errors observed

## Screenshots captured
- ai-dev/active/CR-00036/evidences/post/CR-00036_v2_batch_plan_off.png
- ai-dev/active/CR-00036/evidences/post/CR-00036_v5_merge_button.png
- ai-dev/active/CR-00036/evidences/post/CR-00036_v6_merge_clicked.png
- ai-dev/active/CR-00036/evidences/post/CR-00036_v8_no_regressions.png
- ai-dev/active/CR-00036/evidences/post/CR-00036_v8_batches_list.png

## Root cause (on failures)
- V1 (ENV_DATA_MISSING): No approved items in E2E queue; the "Create batch from selection" action is not accessible from an empty queue page. The fixture creates BATCH-D-0001 directly, but doesn't create an approved item that could trigger the batch creation form.
- V4 (ENV_DATA_MISSING): No batch with status=executing in E2E seed. Cannot open a Plan tab for a running batch to verify the disabled attribute on the auto-merge toggle.
- V7 (ENV_DATA_MISSING): CR-00001's history item shows status "completed" but belongs to BATCH-D-0001 which has auto_merge=false. No item exists in an auto_merge=true completed batch to verify the no-Merge-button regression.

## Fixture gap summary
The e2e_fixtures/001_auto_merge_off_batch.py creates:
- BATCH-D-0001 (planning, auto_merge=false)
- CR-00001 (in awaiting_merge_approval)

To fully verify V1, V4, V7, the fixture should also include:
1. Approved items in the queue (or a method to create a batch from selection)
2. A batch with status=executing and auto_merge=false (for V4 toggle disable check)
3. A batch with status=completed and auto_merge=true with an item whose MERGE step status=completed (for V7 regression check)

## Implementation notes
The CR-00036 implementation appears complete and correct for the aspects that could be verified:
- `auto_merge` column renders in batch header ("Auto-merge: no")
- Plan tab shows toggle pre-filled from batch.auto_merge
- Merge button renders for awaiting_merge_approval items
- Clicking Merge transitions item to completed status
- Restart/Abandon Merge buttons correctly hidden for awaiting_approval state
- Toggle disabled when batch not in planning|approved|paused (template-level check confirmed)


## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: V1, V4, V7 require seed data not in E2E DB — see report

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/CR-00036/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S17` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/CR-00036/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00036/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**ESCALATION**: This is the FINAL browser fix cycle (3/3). **PREFER honest escalation over a Hail-Mary fix that drifts from the design spec.** If you cannot make every failing V pass while staying aligned with the design doc above, document which V's remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
