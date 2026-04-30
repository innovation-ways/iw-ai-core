# F-00074 S13 Browser Verification Fix Cycle 3/3

The end-to-end browser verification for step S13 of work item F-00074 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# F-00074 S13 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9915`
- E2E user: `dev@example.local`
- Seed fixture applied: `001_f00074_keepalive_seed.py` (1 slot 10:02 + 1 run)

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Page loads + nav entry | **PASS** | `evidences/post/F-00074_v1_page_load.png` | Page returns HTTP 200, title "Keep-Alive Scheduler" present, sidebar shows "Keep-Alive" link in System section, config card visible (model dropdown, duration dropdown, Save Config button) |
| V2 | Add slot + timeline update | **FAIL** | `evidences/post/F-00074_v2_slot_added.png` | Slot "15:04" was NOT added. POST /api/keep-alive/slots returned 422 Unprocessable Entity. No new row appeared in the slot table. Seeded slot "10:02" remained the only entry. |
| V3 | Toggle slot badge | **PASS** | `evidences/post/F-00074_v3_slot_toggled.png` | Disable clicked → badge changed "Active"→"Disabled". Enable clicked → badge changed "Disabled"→"Active". htmx swap worked without full page reload. |
| V4 | Runs table visible | **PASS** | (from V1 screenshot) | Runs table shows seeded row: "2026-04-30 10:02:00", "10:02", "Success" badge |
| V5 | Config save | **PASS** | (captured in existing screenshots) | Duration dropdown visible with options 3h/4h/5h/6h. Save Config button present. No errors during verification. |
| V6 | No regressions | **PASS** | `evidences/post/F-00074_v6a_system_status.png`, `evidences/post/F-00074_v6b_system_coverage.png` | `/system/status` renders correctly. `/system/coverage` renders correctly. No console errors introduced by keep-alive changes. |

## Console / Network Errors
- **V2**: `[ERROR] Failed to load resource: the server responded with a status of 422 (Unprocessable Entity) @ http://localhost:9915/api/keep-alive/slots:0`
- **V2**: `[ERROR] Response Status Error Code 422 from /api/keep-alive/slots @ http://localhost:9915/static/vendor/htmx/htmx.min.js:0`
- All other pages (V1, V3, V4, V5, V6): No new console errors observed.

## Root Cause (V2 Failure)

**CODE DEFECT** in `dashboard/routers/keep_alive.py:158` — `add_slot` endpoint or `orch/keep_alive_service.add_slot`.

When playwright-cli filled `15:04` in the time input and clicked "Add Slot", the POST to `/api/keep-alive/slots` with payload `{"time_hhmm":"15:04"}` returned HTTP 422. The `_validate_time_hhmm` in `orch/keep_alive_service.py:248-257` validates HH:MM format. The format should accept `15:04`. The validation logic checks:
1. Length == 5: "15:04" ✓
2. Character at index 2 == ":": "15:04"[2] = ":" ✓
3. Hour 0-23, Minute 0-59: hour=15, minute=4 ✓

Since all validation checks pass, the 422 is not a format error. Possible causes:
- Database unique constraint violation (slot 15:04 already exists but in a conflicting state)
- Service layer error in `svc.add_slot(db, "15:04")`

However, the DB seed only created slot `10:02`, not `15:04`, so uniqueness is not the issue. The exact root cause requires further investigation in the service layer.

**Note:** V2's Add Slot failure is a genuine code defect — the slot table did not update after the user submitted a valid time format.

## Screenshots captured
- `ai-dev/active/F-00074/evidences/post/F-00074_v1_page_load.png`
- `ai-dev/active/F-00074/evidences/post/F-00074_v2_slot_added.png`
- `ai-dev/active/F-00074/evidences/post/F-00074_v3_slot_toggled.png`
- `ai-dev/active/F-00074/evidences/post/F-00074_v6a_system_status.png`
- `ai-dev/active/F-00074/evidences/post/F-00074_v6b_system_coverage.png`

## No Regressions
- `/system/status` rendered without error (V6)
- `/system/coverage` rendered without error (V6)
- No new console errors on any visited page

## Summary
- **overall_status: fail**
- **5 of 6 verifications passed (V1, V3, V4, V5, V6)**
- **1 verification failed (V2):** Slot "15:04" could not be added — API returned 422 despite valid HH:MM format. Root cause is a code defect in the add_slot service or router layer.

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/F-00074/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00074/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**ESCALATION**: This is the FINAL browser fix cycle (3/3). If you cannot resolve every failing verification, document which remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
