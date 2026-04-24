# CR-00020 S15 Browser Verification Fix Cycle 2/3

The end-to-end browser verification for step S15 of work item CR-00020 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# CR-00020 S15 — QvBrowser Report (Fix Cycle 1)

## What was done

S15 is the **QV Browser Verification** step for CR-00020 (Store work item evidences as BLOBs).

The step description was:
> "fixture seeds DB-only work item with pre+post evidence rows; Evidences tab renders both phases without any on-disk directory; image URL serves bytes with DB-stored Content-Type; archived item (no DB rows, no FS) still renders empty cleanly"

## Previous Verification Result

The initial browser verification reported **V1 FAIL** and **V2 FAIL**:

- V1: `_list_evidences()` was reading from filesystem only, not DB-first
- V2: `item_evidence_file()` served from FS only, no DB-first fallback
- V3: **PASS** — archived item returns 404 gracefully

## Fix Applied

The DB-first read path has been implemented in uncommitted changes:

**`dashboard/routers/items.py` changes:**

1. **`_list_evidences()` (line 700):** Now queries `WorkItemEvidence` table DB-first, populates `EvidenceFile` with `content` and `content_type` from DB rows. Falls back to filesystem only for in-progress post-evidence when `worktree_path` is available.

2. **`item_evidence_file()` (line 1254):** Now queries `WorkItemEvidence` DB-first by `(project_id, work_item_id, phase, filename)`. Returns `Response(content=row.content, media_type=row.content_type)` if found. Falls back to filesystem only if DB row not found.

3. **`EvidenceFile` dataclass (line 220):** Added `content: bytes | None` and `content_type: str | None` fields.

4. **Model imports:** Added `EvidencePhase` and `WorkItemEvidence` to imports.

**`orch/db/models.py` changes:**

1. Added `EvidencePhase` enum (`pre`, `post`)
2. Added `WorkItemEvidence` model with BLOB storage for `content` and `content_type`

**New migration:** `orch/db/migrations/versions/d6b67d4ecb9f_add_work_item_evidences.py`

## Test Results

- `test_work_item_evidence.py`: **18/18 passed**
- Full test suite: **1403 passed**
- `mypy dashboard/routers/items.py orch/db/models.py`: **No issues**

## Files Changed (Uncommitted)

- `dashboard/routers/items.py` — DB-first read logic in `_list_evidences()` and `item_evidence_file()`
- `orch/db/models.py` — Added `EvidencePhase` enum and `WorkItemEvidence` model
- `orch/db/migrations/versions/d6b67d4ecb9f_add_work_item_evidences.py` — New migration (untracked)
- `tests/integration/test_work_item_evidence.py` — New test file (untracked)

## Issues/Observations

1. The E2E fixture (`001_cr00020_evidence_fixture.py`) correctly seeds 4 evidence rows in the DB
2. Pre-existing lint errors in E2E fixture (unused imports `io`, `os`, `struct`/`zlib` on one line) are unrelated to functionality
3. The code was already fixed in uncommitted changes when this fix cycle ran — verification was run against stale E2E stack

## Conclusion

CR-00020 S15 DB-first implementation is complete. The `_list_evidences()` and `item_evidence_file()` functions now query `work_item_evidences` table first, with filesystem fallback for in-progress post-evidence only. All tests pass. The orchestrator will rebuild the E2E stack and re-run browser verification.

**Step status: FIX APPLIED — awaiting re-verification**


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
