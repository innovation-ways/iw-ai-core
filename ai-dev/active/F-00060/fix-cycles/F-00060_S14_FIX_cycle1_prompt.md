# F-00060 S14 Browser Verification Fix Cycle 1/2

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

Browser verification was performed against the E2E stack at `http://localhost:9946`. The stack was built from this worktree's source and includes a seeded project (`iw-ai-core`) with work items populated via the baseline seed + F-00060's fixture at `ai-dev/active/F-00060/e2e_fixtures/001_qa_seed.py`.

**Overall status: FAIL** — The re-index button and job creation work correctly, but the Q&A streaming pipeline is non-functional due to an Ollama stub embedding response format mismatch that causes silent failures throughout the retrieval pipeline.

---

## Verification Results

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | Re-index Docs button + jobs view | **PASS** (limited) | Button present and creates a queued job. Job does NOT transition to running/completed because the orch daemon (which includes DocIndexPoller) is not running in the E2E stack. |
| V2 | Originating-item citation + functional snippet | **FAIL** | Q&A streaming returns empty tokens — the Ollama stub embedding format mismatch causes `_embed()` to throw a silent ValidationError that propagates through the pipeline. |
| V3 | Relevance filter drops off-topic items | **FAIL** | Same root cause as V2 — streaming returns empty response. |
| V4 | Allowlist stripping | **FAIL** | Same root cause as V2. No citation panel appears because the answer stream is empty. |
| V5 | Code-only regression | **FAIL** | Streaming returns empty tokens even for code-only questions ("Show me the signature of classify_query"). |
| V6 | No regressions on sibling views | **PASS** | Code, Tests, Quality, Documentation, Jobs pages render without console errors. |

---

## Root Cause Analysis

### Ollama Stub Embedding Response Format Mismatch

The E2E Ollama stub (`scripts/e2e_ollama_stub.py`) implements `POST /api/embeddings` with response:

```json
{"embedding": [-0.052..., 0.017..., ...]}
```

But `llama_index.embeddings.ollama.OllamaEmbedding.get_text_embedding()` (called by `DocIndexer._embed()` at `orch/rag/doc_indexer.py:63`) expects the Ollama API format:

```json
{"model": "stub:latest", "embeddings": [[-0.052..., 0.017..., ...]]}
```

This causes a **Pydantic ValidationError** in the embedding call, which:
1. Causes `DocIndexJobRunner.run()` to catch the exception and mark the job as failed
2. Causes `classify_query` (via `_llm_classify`) to catch the exception and log a warning, falling back to "code_only" (at `orch/rag/classifier.py:104`)
3. But even after falling back to "code_only", the main LLM call in `_stream_chat` also uses `POST /api/chat` which may also have format issues

Dashboard log evidence (`docker logs iw-ai-core-e2e-f00060-e2e-dashboard-1`):
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for EmbedResponse
embeddings
  Field required [type=missing, input_value={'embedding': [...]}]
```

### Daemon Not Running in E2E Stack

The E2E stack's `e2e-dashboard` service runs only `uvicorn dashboard.app:create_app` (see `scripts/e2e_dashboard_entrypoint.sh`). It does NOT start `orch.daemon.main` — the daemon is a **separate process** that runs the poll loop including `DocIndexPoller.poll()`. As a result, even though a `doc_index_jobs` row is created with `status='queued'`, it never transitions to `running` or `completed` because there is no process running `doc_index_poller.poll()` in the E2E stack.

Query against E2E DB confirms the job is stuck at `queued`:
```sql
SELECT id, status FROM doc_index_jobs;
                  id                  | status 
--------------------------------------+--------
 4bd8b752-64d9-43c7-b378-f188f87a1b92 | queued
```

And `daemon_events` table is empty — no daemon poll events have been emitted.

**This is an ENVIRONMENTAL issue**, not a code defect. The E2E stack architecture does not include the orch daemon process.

---

## Screenshots

| File | Description |
|------|-------------|
| `F-00060_v0_code_page_initial.png` | Code page before any interactions |
| `F-00060_v1_reindex_button_open.png` | Dropdown open showing "Re-index Docs" entry |
| `F-00060_v1_jobs_with_doc_index_queued.png` | Jobs view showing doc_indexing job in queued state |
| `F-00060_v1_doc_job_already_running.png` | Re-index Docs click returns "already running" fragment |
| `F-00060_v2_qa_stream_empty.png` | Q&A streaming returns empty (V2 failed) |

All saved to `ai-dev/active/F-00060/evidences/post/`.

---

## No Regressions Observed (V5 + V6)

**V5 (Code-only regression)**: The Q&A surface renders correctly — the textbox, send button, and conversation log are all present. The streaming endpoint returns `event: done` with `{"ok": true}` rather than an error, indicating the pipeline completes without crashing but produces zero content. This is a functional gap, not a UI regression.

**V6 (Sibling views)**: Code page renders with the architecture map. Tests, Quality, Docs, Research, and Jobs pages all render without console errors or 404s.

---

## Code Defects vs Environment Gaps

| Issue | Type | Evidence |
|-------|------|----------|
| doc_index_jobs stuck at `queued` | **ENVIRONMENT** — orch daemon not started in E2E stack | `daemon_events` table empty; E2E entrypoint only starts uvicorn, not `orch.daemon` |
| Q&A streaming returns empty tokens | **ENVIRONMENT** — Ollama stub response format mismatch | Pydantic ValidationError in dashboard logs from `POST /api/embeddings` |
| Re-index Docs "already running" shown when job is queued | **CODE** — Race between stale job check and new job insertion | `reindex_docs` checks for `status IN ('queued','running')` but the old job was never picked up |

The Ollama stub format issue is **not** a code defect in F-00060's implementation — it is that the stub doesn't produce the exact Ollama API format that `llama_index`'s `OllamaEmbedding` client expects. Since the stub is a test fixture (not production code), this would need to be fixed in `scripts/e2e_ollama_stub.py`.

---

## Recommendations

1. **Fix Ollama stub embedding response format** in `scripts/e2e_ollama_stub.py`:
   - Change `POST /api/embeddings` response from `{"embedding": [...]}` to `{"model": "stub:latest", "embeddings": [[...]]}`
   - Or use a real Ollama instance in the E2E stack instead of the stub

2. **Start the orch daemon in the E2E stack** (or document that it is not started and the job lifecycle cannot be tested E2E):
   - Either add a service to `docker-compose.e2e.yml` that runs `uv run python -m orch.daemon`
   - Or update the E2E entrypoint to start both uvicorn AND the daemon

3. **Retest V2, V3, V4, V5** once the embedding format issue is resolved.

---

## Files Changed

- `ai-dev/active/F-00060/e2e_fixtures/001_qa_seed.py` — **CREATED** — seeds work items with functional_doc_content for F-00060-ORIGINAL, CR-00060-RECOLOR, CR-00060-RESHAPE, and one NULL item (F-00060-NULL)
- `ai-dev/active/F-00060/reports/F-00060_S14_BrowserVerification_Report.md` — **CREATED**

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
    {"id": "V1", "name": "reindex button + jobs view", "status": "pass", "screenshot": "F-00060_v1_jobs_with_doc_index_queued.png", "notes": "Button works, job created and visible in Jobs view with job_type=doc_indexing. Job remains queued because orch daemon is not running in E2E stack."},
    {"id": "V2", "name": "originating-item citation + functional snippet", "status": "fail", "screenshot": "F-00060_v2_qa_stream_empty.png", "notes": "Ollama stub embedding format mismatch causes empty streaming response. Pydantic ValidationError in logs."},
    {"id": "V3", "name": "relevance filter drops off-topic items", "status": "fail", "screenshot": "",

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


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
