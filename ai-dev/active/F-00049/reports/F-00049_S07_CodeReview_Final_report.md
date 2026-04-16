# F-00049_S07_CodeReview_Final_report

## Step: S07 — Final Cross-Agent Code Review

**Agent**: code-review-final-impl
**Work Item**: F-00049 — Code Understanding: Q&A Panel (SSE Streaming)
**Verdict**: fail

---

## Summary

All three implementation agents (backend S01, API S03, frontend S05) have delivered their work. The S06 CRITICAL bug (history not saved on stream close) and MEDIUM_FIXABLE XSS issue have been fixed in the current code. However, one new MEDIUM_FIXABLE issue was introduced by the S06 fix: double-push of conversation history on successful SSE completion. This must be fixed before QV gates.

**Test Results**: 742 unit tests passed, 487 integration tests passed, ruff/mypy clean.

---

## Files Changed (from all prior steps)

| File | Action |
|------|--------|
| `orch/rag/qa.py` | Created (S01) |
| `dashboard/routers/code_qa.py` | Created (S03) |
| `dashboard/app.py` | Modified (S03 — registered code_qa router) |
| `dashboard/templates/fragments/code_qa_panel.html` | Created (S05, fixed S06) |
| `dashboard/templates/project_code.html` | Modified (S05 — added data-context-level + include) |
| `tests/unit/test_qa_engine.py` | Created (S01) |
| `tests/integration/test_code_qa_routes.py` | Created (S03) |

---

## Test Results

```
Unit tests:       742 passed, 3 warnings
Integration tests: 487 passed, 15 warnings
Ruff check:      All checks passed (orch/rag/qa.py, dashboard/routers/code_qa.py)
Mypy:            Success, no issues (orch/rag/qa.py, dashboard/routers/code_qa.py)
```

---

## Prior Review Findings Status

| Prior Finding | Severity | Status |
|---------------|----------|--------|
| S06: result.done block didn't save history | CRITICAL | ✅ FIXED — lines 183-189 now push to qaHistory |
| S06: XSS risk via outerHTML in error handler | MEDIUM_FIXABLE | ✅ FIXED — lines 211-216 use safe DOM construction (createElement + textContent) |

---

## New Findings

### 1. Double History Push on Successful SSE Completion

**Severity**: MEDIUM_FIXABLE
**Category**: code_quality
**File**: `dashboard/templates/fragments/code_qa_panel.html`
**Lines**: 183-189 and 204-209

**Description**: The S06 fix added history saving in the `result.done` block (lines 183-189) to fix the CRITICAL bug where history was lost on stream close. However, the `data.event === 'done'` SSE event handler (lines 204-209) also pushes to history. On a successful SSE completion, BOTH handlers fire:

1. Token lines are processed in `forEach` (accumulating `fullResponse`)
2. Server sends `data.event === 'done'` → processed in forEach → history pushed (lines 204-209)
3. `reader.read()` returns `{done: true}` → processed in `result.done` block → history pushed AGAIN (lines 183-189)

Result: 4 history entries (user + assistant × 2) per completed turn instead of 2.

**Impact**: Conversation history grows faster than designed. After N turns, history contains 2N entries instead of N. The trimming at lines 186-188 and 207-208 keeps the array bounded to QA_MAX_HISTORY=10, but entries are duplicated.

**Fix**: Remove history push from the `data.event === 'done'` handler (lines 205-209), keeping only the loading state update. The `result.done` block is the authoritative signal for stream completion and should be the sole history-push point.

```javascript
// In data.event === 'done' handler (lines 204-210):
} else if (data.event === 'done') {
    // History already saved in result.done block — don't push again
    qaSetLoading(false);
}
```

---

### 2. Dead Code: qaErrorBubbleHtml Function

**Severity**: LOW
**Category**: code_quality
**File**: `dashboard/templates/fragments/code_qa_panel.html`
**Lines**: 138-140

**Description**: Function `qaErrorBubbleHtml(message)` is defined but never called. The SSE error handler (lines 211-216) uses safe DOM construction directly instead of this helper. This is leftover from an earlier approach.

**Suggestion**: Remove the unused `qaErrorBubbleHtml` function.

---

## Acceptance Criteria Verification

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Token streaming: answer_stream yields str tokens, API wraps as `data: {"token": "..."}`, frontend appends via textContent | ✅ PASS |
| AC2 | Module filter: engine filters LanceDB by `module_path` when `context_level == "module"` | ✅ PASS |
| AC3 | Architecture context: engine skips filter when `context_level == "architecture"` | ✅ PASS |
| AC4 | History truncation: `_truncate_history()` caps at `MAX_HISTORY_TURNS * 2 = 10` | ✅ PASS |
| AC5 | Ollama unavailable: error propagates to SSE error event → error bubble | ✅ PASS |
| AC6 | Project not found: API returns HTTP 404 before stream starts | ✅ PASS |
| AC7 | No index found: API returns HTTP 404 with correct message | ✅ PASS |
| AC8 | Input validation: Pydantic rejects questions > 1000 chars with 422 | ✅ PASS |
| AC9 | UI collapse: toggle works, icon swaps (▼/▶), label swaps (collapse/expand) | ✅ PASS |
| AC10 | Context label: `qaUpdateContextLabel()` reads `data-context-level` correctly | ✅ PASS |

---

## End-to-End Contract Verification

**SSE Token Flow**:
- `QAEngine.answer_stream()` yields `str` tokens → ✅
- API endpoint wraps tokens as `data: {"token": "..."}\n\n` via `json.dumps` → ✅
- Frontend parses `data.token` and appends via `.textContent` (no XSS) → ✅

**Error Flow**:
- Engine yields `__ERROR__:...` string → ✅
- API detects `__ERROR__:` prefix, yields `data: {"event": "error", "message": "..."}` → ✅
- Frontend replaces bubble with safe DOM construction → ✅

**Done Flow**:
- API yields `data: {"event": "done", "full_response": "..."}` → ✅
- Frontend `data.event === 'done'` handler receives `full_response` → ✅
- BUT: `result.done` block also pushes to history → double-push bug → see finding #1

**Conversation History Flow**:
- JS sends `conversation_history` array → ✅
- API passes as list of dicts to engine → ✅
- Engine `_truncate_history()` caps at 10 → ✅
- Engine converts to `ChatMessage` objects → ✅

---

## Security Cross-Check

- User-supplied text (question, streamed tokens) added via `.textContent` (not `.innerHTML`) → ✅
- `QA_PROJECT_ID` injected via Jinja2 `{{ current_project.id }}` (server-controlled) → ✅
- Error message from SSE parsed and added via `textContent` → ✅
- No hardcoded credentials, no open redirect, no SSRF risks → ✅

---

## Regression Check

- `dashboard/app.py` registers all 17 routers including `code_qa.router` → ✅
- `project_code.html` includes architecture panel, job status panel, and Q&A panel at bottom → ✅
- `orch/rag/__init__.py` not modified → N/A
- No existing routers removed from `app.py` → ✅

---

## Mandatory Fix Count

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM (fixable) | 1 |
| LOW | 1 |
| **Total** | **2** |

**verdict**: fail (due to 1 MEDIUM_FIXABLE finding)
**ready_for_qv_gates**: false

---

## JSON Result

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00049",
  "verdict": "fail",
  "unresolved_prior_findings": [],
  "new_findings": [
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "code_quality",
      "file": "dashboard/templates/fragments/code_qa_panel.html",
      "line": "204-209",
      "description": "The data.event === 'done' handler (lines 204-209) pushes to qaHistory, but the result.done block (lines 183-189) also pushes. On a successful SSE completion (normal case), BOTH handlers fire: the done SSE event is processed in the forEach loop, pushing history, then result.done fires and pushes again. This causes 4 history entries (2 per turn) instead of 2. The result.done fix was necessary to handle stream interruption, but the done SSE event handler should NOT also push since result.done is the authoritative completion signal.",
      "suggestion": "Remove history push from the data.event === 'done' handler (lines 205-209), keeping only qaSetLoading(false). The result.done block is the correct single point for history persistence."
    },
    {
      "severity": "LOW",
      "category": "code_quality",
      "file": "dashboard/templates/fragments/code_qa_panel.html",
      "line": "138-140",
      "description": "Function qaErrorBubbleHtml(message) is defined but never called. The SSE error handler uses safe DOM construction directly (lines 211-216).",
      "suggestion": "Remove the unused qaErrorBubbleHtml function."
    }
  ],
  "ac_verified": {
    "AC1": "pass",
    "AC2": "pass",
    "AC3": "pass",
    "AC4": "pass",
    "AC5": "pass",
    "AC6": "pass",
    "AC7": "pass",
    "AC8": "pass",
    "AC9": "pass",
    "AC10": "pass"
  },
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "742 unit passed, 487 integration passed, 0 failed. Ruff and mypy clean.",
  "ready_for_qv_gates": false,
  "notes": "S06 CRITICAL (history loss) and MEDIUM_FIXABLE (XSS) bugs are fixed. One new MEDIUM_FIXABLE issue (double history push) introduced by the S06 fix. Fix the double-push by removing history push from done event handler (keep only result.done). All 10 ACs verified pass. All tests passing."
}
```
