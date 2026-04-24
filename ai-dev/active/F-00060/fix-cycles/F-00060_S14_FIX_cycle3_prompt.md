# F-00060 S14 Browser Verification Fix Cycle 3/3

The end-to-end browser verification for step S14 of work item F-00060 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# F-00060 S14 Browser Verification Report

**Work Item**: F-00060 — Hybrid Code Q&A retrieval
**Step**: S14
**Agent**: qv-browser
**Base URL used**: `http://localhost:9946`
**Date**: 2026-04-24

---

## Summary

Browser verification was performed against the E2E stack at `http://localhost:9946` built from this worktree's source. The E2E stack was confirmed running with containers `iw-ai-core-e2e-f00060-e2e-dashboard-1`, `iw-ai-core-e2e-f00060-e2e-db-1`, and `iw-ai-core-e2e-f00060-e2e-ollama-1`.

**Overall status: FAIL** (V1 PASS, V2-V5 FAIL due to stub limitations, V6 PASS)

---

## Verification Results

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | Re-index Docs button + jobs view | **PASS** | "Re-index Docs" entry confirmed present in dropdown via template inspection (`project_code.html:73`). Endpoint `POST /project/iw-ai-core/api/code/reindex-docs` correctly creates a `doc_index_jobs` row with `status=queued`. E2E DB query confirms row exists: `('71ed96ca-c1d1-4ca5-9cda-1577d1103bcb', 'iw-ai-core', 'queued', 0, 0, None)`. Job remains queued because the orch daemon is not running in the E2E stack (environmental). The button behavior and job creation are correct. |
| V2 | Originating-item citation + functional snippet | **FAIL** | Q&A streaming with `context_chips=["why"]` triggers workitem_aware path correctly (phase events: `retrieving` → `finding_items` → `reading_docs` → `composing`). However, the Ollama stub (`e2e_ollama_stub.py`) provides only a deterministic echo response ("This is a deterministic stub response for E2E verification — question received: '...'") with no citation events, no functional doc paraphrasing, and no work item ID references. The pipeline infrastructure is correct; the stub lacks real LLM capability. |
| V3 | Relevance filter drops off-topic items | **FAIL** | Same root cause as V2 — stub echoes question without processing the workitem_section context. Cannot verify relevance filtering because the stub doesn't parse work items or emit citations. |
| V4 | Allowlist stripping | **FAIL** | Same root cause as V2 — no citation events are emitted by the stub. The pipeline infrastructure (allowlist wiring in `qa.py:600-614`) is correct but cannot be verified with a non-functional stub. V4 notes: hallucination is non-deterministic; the deterministic unit test `tests/unit/test_qa_v2_allowlist_wiring.py` covers the allowlist invariant. |
| V5 | Code-only regression | **PASS** | Code-only questions (e.g., "Show me the signature of classify_query") correctly route to the `code_only` branch. Streaming works (tokens + `event: done`). No "Work Item Context" section injected. UI renders correctly. Note: the stub response is the same shallow echo regardless of classification, so behavioral difference is not observable in this E2E env. |
| V6 | No regressions on sibling views | **PASS** | Jobs page renders correctly with existing job rows. Tests, Quality, Docs pages all render without console errors. |

---

## Root Cause Analysis

### V2-V5: Ollama Stub Lacks Real LLM Capability

The E2E environment uses `scripts/e2e_ollama_stub.py` which provides deterministic fake responses that verify the pipeline architecture (events flow, tokens stream, phase transitions work) but do not exercise the full workitem-aware RAG logic (citation emission, functional doc paraphrasing, relevance filtering).

With `context_chips=["why"]` forcing workitem_aware classification:
1. `classify_query()` returns `"workitem_aware"` → correct
2. `_retrieve_evidence_bundle()` runs → correctly finds work items from FTS/LanceDB
3. `_build_workitem_system_prompt()` adds Work Item Context section → correct
4. Phase events fire: `retrieving` → `finding_items` → `reading_docs` → `composing` → correct
5. Token stream begins → correct
6. **BUT**: stub response is just `"This is a deterministic stub response..."` → no citations, no paraphrasing

The actual implementation (`qa.py:585-599` + `600-614`) correctly:
- Streams tokens from LLM response
- Filters through `citation_allowlist.filter_citations`
- Emits citation events for mentioned IDs that are in `allowed_ids`

But the stub never generates citation-worthy content, so no citation events are emitted.

### V1: DocIndexJob Stuck at Queued (Environmental)

The `doc_index_jobs` row is created correctly (`status=queued`). The job never transitions to `running` because `orch.daemon.main` is a separate process not started in `e2e_dashboard_entrypoint.sh`. This is by design for isolated E2E testing — only uvicorn dashboard is started, not the full orchestration daemon.

---

## Streaming Verification Evidence

**Workitem-aware with `context_chips=["why"]`** (curl to E2E endpoint):
```
event: phase
data: {"name": "retrieving", "detail": {"count": 0, "symbol": ""}}

event: phase
data: {"name": "finding_items", "detail": {"count": 1, "symbol": ""}}

event: phase
data: {"name": "reading_docs", "detail": {"count": 1}}

event: phase
data: {"name": "composing", "detail": {"render_id": "abc123", "count": 1}}

event: token
data: {"b64": "VGhpcw=="}  → "This"
event: token
data: {"b64": "IGlz"}      → "is"
... (tokens stream correctly)
event: done
data: {"ok": true}
```

**Code-only question** (no context_chips):
```
event: token
data: {"b64": "VGhpcw=="}  → "This"
... (tokens stream)
event: done
data: {"ok": true}
```

Both paths stream tokens correctly. The phase events prove the workitem_aware branch is entered. The stub response confirms the pipeline executes but lacks real LLM depth.

---

## E2E DB Seed Data Confirmation

Query against E2E DB (port 5478, `iw_e2e` database):
```
CR-00060-RECOLOR | functional_doc_content populated (blue recoloring, #3b82f6)
CR-00060-RESHAPE | functional_doc_content populated (shape change)
F-00060-NULL     | functional_doc_content = NULL (AC4 fallback test)
F-00060-ORIGINAL | functional_doc_content populated (green button, #10b981)
```

All seed items present and correct.

---

## Screenshot Evidence

| File | Description |
|------|-------------|
| `F-00060_v0_code_page_initial.png` | Code page on initial load (saved from playwright-cli) |
| `F-00060_v1_jobs_page.png` | Jobs page showing existing jobs (reindex button verified via code inspection + curl, not visible in playwright snapshots) |

---

## Code Defects vs Environment Gaps

| Issue | Type | Evidence |
|-------|------|----------|
| V1: re-index button creates job but job stays queued | **ENVIRONMENT** — orch daemon not in E2E stack | `e2e_dashboard_entrypoint.sh` only starts uvicorn, not daemon. Job creation works correctly. |
| V2-V5: workitem-aware questions don't emit citations | **ENVIRONMENT** — Ollama stub lacks real LLM | Stub produces echo responses; pipeline infrastructure (classification, retrieval, phase events, allowlist wiring) is correct. Real Ollama with proper model would produce citations. |

---

## No Regressions Observed (V5 + V6)

**V5 (Code-only regression)**: Code-only questions stream tokens correctly and do not inject workitem context. The streaming pipeline (`answer_stream_v2` → `answer_stream` for `code_only`) works as expected. No UI regressions.

**V6 (Sibling views)**: Jobs, Tests, Quality, Docs pages render without console errors. No regressions to existing functionality.

---

## Files Changed

- No files were modified during this verification step.
- Screenshots saved to `ai-dev/active/F-00060/evidences/post/`.

---

## JSON Report (Subagent Result Contract)

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "F-00060",
  "overall_status": "fail",
  "base_url_used": "http://localhost:9946",
  "verifications": [
    {"id": "V1", "name": "reindex button + jobs view", "status": "pass", "screenshot": "F-00060_v1_jobs_page.png", "notes": "Re-index Docs entry present in dropdown (confirmed via template + curl). POST endpoint creates queued doc_index_jobs row. Job remains queued due to daemon not running (environmental)."},
    {"id": "V2", "name": "originating-item citation + f

...(report truncated for prompt length)...

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/F-00060/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00060/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**ESCALATION**: This is the FINAL browser fix cycle (3/3). If you cannot resolve every failing verification, document which remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
