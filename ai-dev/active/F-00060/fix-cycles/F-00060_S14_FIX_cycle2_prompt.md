# F-00060 S14 Browser Verification Fix Cycle 2/2

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

Browser verification was performed against the E2E stack at `http://localhost:9946`. The stack was built from this worktree's source and includes a seeded project (`iw-ai-core`) with work items.

**Overall status: FAIL**

V1 (Re-index button) passes. V2, V3, V4, V5 all FAIL because the Q&A streaming pipeline returns an empty response. V6 (sibling views) passes.

---

## Verification Results

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | Re-index Docs button + jobs view | **PASS** | Button "Re-index Docs" is present in the dropdown below "Re-index changed files". Clicking it creates a `doc_index_jobs` row with status=queued, visible in the Jobs view with job_type=doc_indexing. Job remains queued because the orch daemon is not running in the E2E stack (this is environmental). |
| V2 | Originating-item citation + functional snippet | **FAIL** | Q&A streaming returns empty tokens. The `/api/projects/iw-ai-core/code/qa` endpoint returns HTTP 200 but the SSE stream only contains `event: done\ndata: {"ok": true}` with zero content events preceding it. |
| V3 | Relevance filter drops off-topic items | **FAIL** | Same root cause as V2 — streaming returns empty. Cannot verify relevance filtering because no content is emitted. |
| V4 | Allowlist stripping | **FAIL** | Same root cause as V2. No citation panel appears because the answer stream is empty. |
| V5 | Code-only regression | **FAIL** | Streaming returns empty tokens even for code-only questions ("Show me the signature of classify_query"). The answer shows "Assistant" with no content, no "Work Item Context" section appears (expected), but the streaming is empty rather than containing the stub's deterministic response. |
| V6 | No regressions on sibling views | **PASS** | Tests, Quality, Docs, Research, Jobs pages render without console errors. |

---

## Root Cause Analysis

### Q&A Streaming Returns Empty Content

The root cause is in the server-side Q&A streaming pipeline in `orch/rag/qa.py`. When I curl the Q&A endpoint directly:

```bash
curl -X POST "http://localhost:9946/api/projects/iw-ai-core/code/qa" \
  -H "Content-Type: application/json" \
  -d '{"question":"When was the New project button created? What does it do?","context_level":"architecture"}'
```

The response is:
```
event: done
data: {"ok": true}
```

This is just the terminal event — no content events are emitted before it. The streaming completes with `ok: true` but produces zero answer tokens. This happens for ALL question types, including code-only questions.

**Ollama itself works correctly**:
- `curl http://localhost:11434/api/tags` returns model list
- `curl -X POST http://localhost:11434/api/embeddings -d '{"model":"qwen3-embedding:8b","prompt":"test"}'` returns a valid embedding vector
- `curl -X POST http://localhost:11434/api/chat -d '{"model":"qwen3:4b","messages":[{"role":"user","content":"hi"}]}'` returns streaming NDJSON

The problem is in the dashboard's `orch/rag/qa.py` streaming logic — it correctly calls Ollama and gets a response, but fails to emit any content events to the SSE stream before completing.

This is a **CODE DEFECT** — the streaming pipeline in the dashboard has a bug where content events are not being emitted.

### Re-index Job Stuck at Queued (Environmental)

The `doc_index_jobs` row created by clicking "Re-index Docs" shows status=queued and never transitions to running/completed because the orch daemon (which runs `DocIndexPoller`) is not started in the E2E stack's `e2e-dashboard` service.

The E2E entrypoint (`scripts/e2e_dashboard_entrypoint.sh`) only starts `uvicorn dashboard.app:create_app`. The `orch.daemon.main` is a separate process and is not included in the E2E stack.

This is an **ENVIRONMENTAL** issue — no code fix can make the job complete without the daemon running.

---

## Screenshots

| File | Description |
|------|-------------|
| `F-00060_v0_code_page_initial.png` | Code page on initial load |
| `F-00060_v1_reindex_complete.png` | Jobs page showing doc_indexing job (queued) + code_mapping job (completed) |
| `F-00060_v1_jobs_with_doc_index_queued.png` | Same as above - jobs view |

---

## No Regressions Observed (V5 + V6)

**V5 (Code-only regression)**: The Q&A surface renders correctly — the textbox, send button, and conversation log are all present. The streaming endpoint returns `event: done` with `{"ok": true}` rather than an error, indicating the pipeline completes without crashing but produces zero content. The lack of "Work Item Context" section in the empty response is consistent with the expected behavior (code-only mode should not inject work item context). This is a functional gap, not a UI regression.

**V6 (Sibling views)**: Tests page renders correctly. Quality page renders correctly. The navigation, content areas, and action buttons all appear correctly.

---

## Code Defects vs Environment Gaps

| Issue | Type | Evidence |
|-------|------|----------|
| Q&A streaming returns empty tokens | **CODE DEFECT** — `orch/rag/qa.py` streaming logic bug | Direct curl to `/api/projects/iw-ai-core/code/qa` returns `event: done` with no preceding content events. Ollama itself works correctly when called directly. |
| doc_index_jobs stuck at `queued` | **ENVIRONMENT** — orch daemon not started in E2E stack | `daemon_events` table empty; E2E entrypoint only starts uvicorn, not `orch.daemon` |

---

## Recommendations

1. **Fix Q&A streaming in `orch/rag/qa.py`** — the streaming response is empty despite Ollama returning valid content. The pipeline between Ollama's response and the SSE emission needs investigation. Check `answer_stream_v2` and `_stream_chat` in `orch/rag/qa.py` for issues with event emission.

2. **Start orch daemon in E2E stack** OR **mock the doc_index_poller** in tests so job lifecycle can be verified.

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
    {"id": "V1", "name": "reindex button + jobs view", "status": "pass", "screenshot": "F-00060_v1_reindex_complete.png", "notes": "Re-index Docs button present and creates a queued doc_index_jobs row visible in Jobs view with job_type=doc_indexing. Job remains queued because orch daemon is not running in E2E stack (environmental)."},
    {"id": "V2", "name": "originating-item citation + functional snippet", "status": "fail", "screenshot": "", "notes": "Q&A streaming returns empty tokens. SSE stream contains only 'event: done' with no preceding content events. CODE DEFECT in orch/rag/qa.py streaming logic."},
    {"id": "V3", "name": "relevance filter drops off-topic items", "status": "fail", "screenshot": "", "notes": "Same root cause as V2 — streaming returns empty. Cannot verify."},
    {"id": "V4", "name": "allowlist stripping", "status": "fail", "screenshot": "", "notes": "Same root cause as V2 — streaming returns empty. No citation panel appears."},
    {"id": "V5", "name": "code-only regression", "status": "fail", "screenshot": "", "notes": "Streaming returns empty tokens even for code-only questions. The answer shows 'Assistant' with no content. No Work Item Context section present (expected), but streaming should contain stub response content."},
    {"id": "V6", "name": "no regressions on sibling views", "status": "pass", "screenshot": "", "notes": "Tests, Quality, Docs, Research, Jobs pages render without console errors."}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "F-00060_v0_code_page_initial.png",
    "F-00060_v1_reindex_complete.png",
    "F-

...(report truncated for prompt length)...

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/F-00060/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**ESCALATION**: This is the FINAL browser fix cycle (2/2). If you cannot resolve every failing verification, document which remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
