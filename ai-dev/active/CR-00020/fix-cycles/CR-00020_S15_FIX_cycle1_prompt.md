# CR-00020 S15 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S15 of work item CR-00020 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# CR-00020 S15 — QvBrowser Report

## What was done

S15 is the **QV Browser Verification** step for CR-00020 (Store work item evidences as BLOBs).

The step description was:
> "fixture seeds DB-only work item with pre+post evidence rows; Evidences tab renders both phases without any on-disk directory; image URL serves bytes with DB-stored Content-Type; archived item (no DB rows, no FS) still renders empty cleanly"

**Execution:**

1. Created E2E fixture `ai-dev/active/CR-00020/e2e_fixtures/001_cr00020_evidence_fixture.py` that seeds:
   - A `CR-00020-TEST` work item (approved, active) with all S01-S15 workflow steps completed
   - 4 `WorkItemEvidence` rows (2 pre-phase, 2 post-phase) with minimal valid PNG content
   - A `Batch` + `BatchItem` to give `worktree_path` non-None value

2. Ran `scripts/e2e_seed.py` inside the E2E container to apply the fixture.

3. Ran `playwright-cli` browser verification against `http://localhost:9955`:
   - V1: Navigate to `/project/iw-ai-core/item/CR-00020-TEST/tab/evidences`
   - V2: Navigate to `/project/iw-ai-core/item/CR-00020-TEST/evidence/post/post_qvbrowser_v1.png`
   - V3: Simulate archived item (no DB rows scenario)

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Evidences tab renders DB-sourced evidence rows | **FAIL** | `evidences/post/CR-00020_v1_evidences_tab.png` | Shows "No evidences captured for this item" — `_list_evidences()` still reads from filesystem only, not DB-first |
| V2 | Image URL serves bytes from DB content | **FAIL** | `evidences/post/CR-00020_v1_empty_evidences.png` | Returns `{"detail":"Evidence file not found"}` — `item_evidence_file()` serves from FS only, no DB-first fallback |
| V3 | Archived item (no DB rows, no FS) renders empty cleanly | **PASS** | n/a | Returns 404, which is graceful |

## Screenshots captured

- `ai-dev/active/CR-00020/evidences/post/CR-00020_v1_evidences_tab.png` — Evidences tab showing "No evidences captured"
- `ai-dev/active/CR-00020/evidences/post/CR-00020_v1_empty_evidences.png` — Evidence file URL showing 404

## Root cause

**The dashboard evidence browser (`_list_evidences` + `item_evidence_file`) has NOT been updated to read from DB-first.**

CR-00020's S05 (API) concluded "no action needed" because the schema was already added, but the actual DB-first read logic in `dashboard/routers/items.py:696` (`_list_evidences`) and `dashboard/routers/items.py:1229` (`item_evidence_file`) was never implemented. The E2E DB **has** the 4 `work_item_evidences` rows for `CR-00020-TEST` (verified via direct query), but the dashboard still reads exclusively from `ai-dev/active/<id>/evidences/{pre,post}/` on disk — which doesn't exist for the fixture item.

## Files changed

- `ai-dev/active/CR-00020/e2e_fixtures/001_cr00020_evidence_fixture.py` — **created** (E2E fixture for CR-00020-TEST)
- `ai-dev/active/CR-00020/evidences/post/CR-00020_v1_evidences_tab.png` — **created** (screenshot)
- `ai-dev/active/CR-00020/evidences/post/CR-00020_v1_empty_evidences.png` — **created** (screenshot)

## Issues or observations

1. **CR-00020 DB-first implementation is incomplete** — The `WorkItemEvidence` table and `EvidencePhase` enum exist in the schema, but `dashboard/routers/items.py:_list_evidences()` and `item_evidence_file()` still serve exclusively from the filesystem. The DB-first read + FS-fallback logic described in the CR-00020 design doc has not been implemented.

2. **E2E fixture correctly seeds evidence rows** — Verified via direct psycopg query: 4 rows exist in the E2E DB (`work_item_evidences` table) for `CR-00020-TEST`. The fixture code is correct.

3. **S05 conclusion was incorrect** — S05 stated "no action needed" because the schema was complete. However, the DB-first read path for the dashboard was explicitly in CR-00020's scope (see design doc: "Dashboard reads from DB: `_list_evidences()` queries the new table").

4. **Pre-existing failures (S14)** remain unrelated — 52 pre-existing OSS/scan test failures in `project_oss_job.base_sha` schema mismatch (not CR-00020 related).

## Conclusion

CR-00020 S15 (QV Browser) **failed**.

The DB-first evidence browser implementation is not complete. The `_list_evidences()` and `item_evidence_file()` functions in `dashboard/routers/items.py` need to be updated to query `work_item_evidences` table first, with filesystem fallback for in-progress post-evidence only.

The E2E fixture correctly seeds 4 evidence rows in the DB, but the dashboard UI still reads exclusively from disk (`ai-dev/active/<id>/evidences/`), which is empty for `CR-00020-TEST`.

**Fix required**: Update `dashboard/routers/items.py:_list_evidences()` and `item_evidence_file()` to implement the DB-first read path with FS fallback as described in the CR-00020 design doc.

**Step status: FAILED** (code defect — missing DB-first implementation, not environment gap)

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/CR-00020/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00020/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
