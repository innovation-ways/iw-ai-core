# F-00091 S09 Code Review Report

## Summary
Reviewed S01/S02/S03/S04/S06/S07/S08 against AC1–AC4 and Invariants 1–7.

Pre-review gates executed first:
- `make lint` ✅
- `make format-check` ✅

All required step files are present (including required paths per step), and migration/test artifacts exist.

## Findings

1. **CRITICAL — contract/correctness**  
   **Path:** `dashboard/routers/chat.py`  
   `GET /api/chat/tabs/{tab_id}` still returns HTTP 503 before payload shaping when runtime is unhealthy (OpenCode and Pi), so `session.context_pct_status` is not always emitted as required by S06/design boundary behavior (`unknown_runtime` payload branch expected).

2. **CRITICAL — invariant violation (I2)**  
   **Path:** `dashboard/static/chat_assistant/chat.js`  
   `_assistantProjectId()` re-reads `localStorage.getItem('iw-chat-assistant-project')` on every call. This violates the invariant expectation of stable per-load reads / single read lifecycle semantics.

3. **HIGH — threshold logic mismatch**  
   **Path:** `dashboard/static/chat_assistant/chat.js`  
   `_applyContextPct` class thresholds use `rounded` percentage. Values like 89.5 become 90 and flip to red, conflicting with specified color bands based on actual percentage (green <70, amber 70–89, red >=90).

4. **MEDIUM — checklist/doc expectation miss**  
   **Path:** `dashboard/static/chat_assistant/chat.js`  
   `_browserTabId` was removed but without the requested one-line documentation note/TODO explaining the removal intent in S03 checklist.

5. **MEDIUM — functional doc rule violation**  
   **Path:** `ai-dev/active/F-00091/F-00091_Functional.md`  
   Functional summary is over the 500-word limit (measured ~561 words), violating the stated review constraint.

## Additional Notes
- S01 endpoint behavior (enabled-only, sorted by `lower(display_name)`, empty list 200) is correct.
- S04 migration is idempotent (`WHERE context_window_tokens IS NULL`) and downgrade is NULL-revert-only.
- S07 UI structure/CSS placement and unknown-state rendering are implemented in the intended files.
- S08 includes the 3 cross-step test files; one expected branch is currently `xfail` due to the runtime-503 behavior above.

## Files Reviewed (primary)
- `dashboard/routers/chat.py`
- `dashboard/static/chat_assistant/chat.js`
- `dashboard/static/chat_assistant/chat.css`
- `dashboard/templates/chat_assistant/panel.html`
- `dashboard/templates/chat_assistant/composer.html`
- `orch/chat/context_usage.py`
- `orch/db/migrations/versions/76250ecb2593_f_00091_backfill_pi_context_window_.py`
- `tests/dashboard/test_api_chat_projects.py`
- `tests/dashboard/test_assistant_project_decoupling.py`
- `tests/dashboard/test_active_tab_restoration.py`
- `tests/dashboard/test_chat_tabs_status_payload.py`
- `tests/dashboard/test_context_pct_progress_bar.py`
- `tests/dashboard/test_chat_panel_html_smoke.py`
- `tests/unit/test_context_usage_status.py`
- `tests/integration/test_alembic_chat_context_backfill.py`
- `tests/integration/test_chat_panel_project_decoupling.py`
- `tests/integration/test_chat_tabs_context_pct_payload.py`
