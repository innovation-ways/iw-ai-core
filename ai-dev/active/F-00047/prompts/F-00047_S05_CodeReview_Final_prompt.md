# F-00047 S05 — Final Cross-Agent Code Review

## Mission

Perform a holistic review of all code and templates produced in F-00047 (S01 + S03). Verify that the API layer and the frontend layer work together correctly. Check for integration issues, missing wiring, and anything that would prevent the feature from functioning end-to-end.

## Required Reading

1. `CLAUDE.md` — architecture rules and critical constraints
2. `dashboard/CLAUDE.md` — dashboard conventions
3. `ai-dev/active/F-00047/F-00047_Feature_Design.md` — complete feature specification
4. All files created or modified in this feature:
   - `dashboard/routers/code_ui.py` (S01)
   - `dashboard/app.py` (S01 — router registration)
   - `dashboard/templates/base.html` (S03 — Mermaid script)
   - `dashboard/templates/fragments/nav_projects.html` (S03 — Code nav link)
   - `dashboard/templates/project_code.html` (S03)
   - `dashboard/templates/fragments/code_job_status.html` (S03)
   - `dashboard/templates/fragments/code_empty_state.html` (S03)
   - `dashboard/templates/fragments/code_architecture_view.html` (S03)
   - `dashboard/templates/fragments/code_job_report.html` (S03)
   - `tests/unit/test_code_ui_routes.py` (S01)
   - `tests/integration/test_code_sse.py` (S01)

## Cross-Cutting Review Checklist

### Scope Boundary (Option C)
- [ ] F-00047 owns ALL HTTP routes and SSE streaming for the code tab. Exactly one router module exists: `dashboard/routers/code_ui.py`.
- [ ] There is NO `dashboard/routers/code.py` file. If it exists (from an earlier draft of F-00046), it must be deleted — F-00046 is library-only.
- [ ] F-00046 exposes `start_index_job`, `JOB_REGISTRY`, `CodeIndexJobRunner`, `JobAlreadyRunningError` via `orch.rag.job`; F-00047 imports and uses them but does not reimplement them.

### API ↔ Template Contract
- [ ] Route handler for `GET /project/{id}/code` passes all context variables expected by `project_code.html`:
  - `current_project`, `index_status`, `running_job`, `last_completed_job`, `last_completed_recent`, `last_completed_duration`, `arch_doc`, `content_html`
- [ ] Both Route 1 (`GET /code`) and Route 3 (`GET /api/code/architecture`) call the same `_render_architecture_html(arch_doc)` helper — no duplicated mermaid pre-processing
- [ ] Route handler for `GET /project/{id}/api/code/architecture` passes all context variables expected by `code_architecture_view.html`:
  - `content_html` (pre-processed HTML with Mermaid blocks replaced), `current_project`, `arch_doc`
- [ ] Route handler for `GET /project/{id}/api/code/status` passes context for both `code_job_status.html` and `code_empty_state.html`
- [ ] Route handlers for POST actions return `code_job_status.html` with correct context (`running_job`, `current_project`)
- [ ] Every field referenced in templates corresponds to an actual column on `CodeIndexJob` in `orch/db/models.py`: `llm_model`, `embed_model`, `files_indexed`, `chunks_created`, `languages_detected`, `doc_id`, `triggered_at`, `completed_at`, `errors`, `status`. Flag any reference to `chat_model`, `job_type`, `languages_json`, `level1_doc`, `duration_formatted`, or `completed_recently` as CRITICAL — those names do not exist on the model.

### URL Consistency
- [ ] All `hx-post` URLs in templates match router paths defined in `code_ui.py`
- [ ] SSE stream URL in `code_job_status.html` JS matches the `GET /project/{id}/api/code/index/stream` route
- [ ] `htmx.ajax()` refresh URLs in the EventSource `done` handler match route paths
- [ ] Nav link URL `/project/{id}/code` matches the `GET /project/{id}/code` page route

### State Machine Completeness
- [ ] Empty state shown correctly when no completed job exists
- [ ] Job status panel shown when a job is running
- [ ] Completion report shown when most-recent job completed (not just any historical job)
- [ ] Architecture view shown when `content_html` is non-null (the ProjectDoc referenced by `CodeIndexJob.doc_id` exists and was pre-rendered). The template guards on `content_html`, not on the raw markdown.
- [ ] Transition from running → completed: SSE `done` event triggers refresh of both panels

### SSE Correctness
- [ ] `data: {json}\n\n` format (exactly two newlines) in all events from the stream endpoint
- [ ] Stream closes cleanly on both `done` events and client disconnect (`asyncio.CancelledError`)
- [ ] EventSource in JS closes on both `done` event and `onerror`
- [ ] No memory leak: elapsed timer interval is cleared when EventSource closes or panel is removed from DOM

### Error Handling
- [ ] 409 returned by POST routes when `start_index_job` raises `JobAlreadyRunningError` (explicit catch, not generic 500)
- [ ] SSE endpoint handles the case where `project_id` is absent from `JOB_REGISTRY` (emit `{"event":"done","status":"idle"}` and close)
- [ ] Template renders gracefully when `index_status` is None (no crash)
- [ ] Template renders gracefully when `index_status.level1_doc_markdown` is None (shows empty state, not an error)

### Test Coverage
- [ ] Unit tests exist for all 8 routes (page, status, architecture, stream, index, reindex, regen-map, cancel)
- [ ] Cancel endpoint tested for both the running-job case (404 runner check → request_cancel called, fragment returned) and the no-job case (404)
- [ ] Integration test covers SSE stream endpoint with actual DB
- [ ] No test connects to live DB on port 5433

### No Regressions
- [ ] `base.html` changes (Mermaid script) do not break any existing page
- [ ] `nav_projects.html` change does not break existing nav for projects without a code index
- [ ] `dashboard/app.py` router registration does not conflict with existing routers (no prefix overlap)

## Output Format

```
## Final Review Result: PASS | FAIL | PASS WITH NOTES

### Blocking Issues (must fix before QV gates)
- <file>:<line> — description

### Non-Blocking Issues (fix when possible)
- <file>:<line> — description

### Integration Gaps
- ...

### Security / Performance Notes
- ...

## Verdict
APPROVED FOR QV GATES | NEEDS FIXES FIRST
```

If the verdict is NEEDS FIXES FIRST, list every change required and which agent owns it (api-impl or frontend-impl).
