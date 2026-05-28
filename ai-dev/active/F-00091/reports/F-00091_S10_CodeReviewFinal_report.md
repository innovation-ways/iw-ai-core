# F-00091 S10 — CodeReview Final

## What I reviewed
Cross-step integration consistency across S01/S02/S03/S04/S06/S07/S08, plus S09 CRITICAL/HIGH follow-up verification.

## Pre-final gates
- `make lint` ✅
- `make format-check` ✅

## Cross-cutting results
- Wire compatibility checks passed:
  - S02 fetches `/api/chat/projects`; S01 registers `@router.get("/projects")` under `/api/chat`.
  - S06 session payload keys match S07 consumer keys exactly: `context_pct_status`, `used_tokens`, `window_tokens`, `context_pct_reason`.
  - S02/S03 localStorage key strategy is non-conflicting and intentional (`iw-chat-assistant-project` vs `iw-chat-active-tab:<projectId>`).
- Existing chat features remain present in `chat.js`:
  - Settings runtime/model controls still wired.
  - Slash-menu loader still wired.
  - Tab context menu (rename/duplicate/close) still wired.
  - `/api/chat/tabs` still returns `default_runtime`.
- Conventions/style checks passed for this change set (ES5 IIFE style, CSS in `chat.css`, no new Jinja `format` misuse observed).

## Findings
1. **CRITICAL · regression/wire-compat**  
   **Path:** `dashboard/routers/chat.py` (`get_tab`)  
   **Summary:** S09 CRITICAL remains unresolved. For Pi tabs, unhealthy runtime still returns HTTP 503 before shaping `session`, so `context_pct_status="unknown_runtime"` payload branch is not emitted.

2. **CRITICAL · conventions/regression**  
   **Path:** `dashboard/static/chat_assistant/chat.js` (`_assistantProjectId`)  
   **Summary:** S09 CRITICAL remains unresolved. `_assistantProjectId()` still re-reads localStorage each call instead of stable per-load state, violating the documented invariant.

3. **CRITICAL · regression/UI contract**  
   **Path:** `dashboard/static/chat_assistant/chat.js` (`_applyContextPct`)  
   **Summary:** S09 HIGH remains unresolved and is escalated per S10 instructions. Threshold classes use rounded percent (`Math.round`) so values like 89.5 become red (>=90), conflicting with specified color bands on actual percentage.

4. **MEDIUM · perf**  
   **Path:** `orch/db/migrations/versions/76250ecb2593_f_00091_backfill_pi_context_window_.py`  
   **Summary:** Migration uses a Python loop issuing multiple UPDATEs (one per tuple), not a single set-based batch UPDATE as requested in the cross-cutting checklist.

## Notes
- AC automation exists for most branches, but unknown-runtime Pi coverage is currently marked `xfail` in integration due to the unresolved 503 behavior above.

## Result contract
```json
{
  "step": "S10",
  "agent": "code-review-final-impl",
  "work_item": "F-00091",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/work/F-00091/reports/F-00091_S10_CodeReview_Final_report.md",
    "ai-dev/active/F-00091/reports/F-00091_S10_CodeReviewFinal_report.md"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "skipped:review-only",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "review-only step; no tests run",
  "tdd_red_evidence": "n/a — review step",
  "findings": [
    {"severity": "CRITICAL", "category": "wire-compat", "path": "dashboard/routers/chat.py", "summary": "get_tab still returns 503 for unhealthy Pi runtime instead of unknown_runtime session payload"},
    {"severity": "CRITICAL", "category": "conventions", "path": "dashboard/static/chat_assistant/chat.js", "summary": "_assistantProjectId still re-reads localStorage each call; invariant unresolved"},
    {"severity": "CRITICAL", "category": "regression", "path": "dashboard/static/chat_assistant/chat.js", "summary": "_applyContextPct thresholds use rounded pct; 89.5% incorrectly flips to red"},
    {"severity": "MEDIUM", "category": "perf", "path": "orch/db/migrations/versions/76250ecb2593_f_00091_backfill_pi_context_window_.py", "summary": "migration uses per-row UPDATE loop, not one set-based batch UPDATE"}
  ],
  "blockers": [],
  "notes": "Escalated unresolved S09 CRITICAL/HIGH items per S10 rules."
}
```