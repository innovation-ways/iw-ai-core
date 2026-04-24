# I-00037 S13 Browser Verification Fix Cycle 2/3

The end-to-end browser verification for step S13 of work item I-00037 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# I-00037 S13 Browser Verification Report

**Step:** S13
**Agent:** qv-browser
**Work Item:** I-00037
**Date:** 2026-04-24

## Environment

- **Base URL:** `http://localhost:9947`
- **E2E credentials:** `dev@example.local` (password not logged)
- **Project:** `iw-ai-core`

## Summary

Verification could not proceed — the E2E stack was provisioned before the fixture file was created.

## Verifications

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | Dashboard home shows 30% | FAIL | No active batches visible — fixture not loaded |
| V2 | Batches view shows 30% | FAIL | No active batches visible — fixture not loaded |
| V3 | Parity between home and batches view | FAIL | Both pages empty — parity cannot be established |
| V4 | No regressions (detail/queue/history/console) | FAIL | Pages render but fixture data absent |

## Fixture Added

File created: `ai-dev/active/I-00037/e2e_fixtures/001_partial_progress_batch.py`

The fixture creates:
- Work item `I-TEST-37` with 10 `WorkflowStep` rows (steps 1-3 completed, steps 4-10 pending)
- Batch `BATCH-TEST37` with `BatchStatus.executing`
- One `BatchItem` linking `I-TEST-37` to `BATCH-TEST37` with `BatchItemStatus.in_progress`

Expected post-fix reading: **30%** (3 completed / 10 total steps)

## Action Required

The daemon must **re-provision** the E2E stack so the seed script runs with the new fixture file present. Once re-provisioned, this step should be re-run to verify:

1. V1: Dashboard home shows `BATCH-TEST37` with 30% step-based progress
2. V2: Batches view shows `BATCH-TEST37` at 30%
3. V3: Both views agree on 30% (parity confirmed)
4. V4: Detail, queue, history pages render cleanly with no console errors

## Failure Reason

```
ENV_DATA_MISSING: seeded BATCH-TEST37 not visible on /project/iw-ai-core/ —
fixture ai-dev/active/I-00037/e2e_fixtures/001_partial_progress_batch.py was
missing from the worktree when the E2E stack was provisioned. Fixture has now
been added; daemon must re-provision to reload the seed script with the new
fixture.
```

## Screenshots

No screenshots captured — verification did not proceed past the empty-state confirmation.

## Comparison Against Pre-fix Evidence

- Pre-fix dashboard home showed **0%** (`evidences/pre/I-00037-dashboard-home-shows-0pct.png`)
- Pre-fix batches view showed **94%** (`evidences/pre/I-00037-batches-view-shows-correct-pct.png`)
- Post-fix (when re-provisioned) should show **30%** in BOTH views — eliminating the inconsistency

---

**Overall Status:** FAIL — ENV_DATA_MISSING (re-provision required)

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/I-00037/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00037/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
