# F-00049_S07_CodeReview_Final_prompt

**Work Item**: F-00049 — Code Understanding: Q&A Panel (SSE Streaming)
**Step**: S07
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/F-00049/F-00049_Feature_Design.md` — Design document
- `ai-dev/work/F-00049/reports/F-00049_S01_Backend_report.md` — S01 report
- `ai-dev/work/F-00049/reports/F-00049_S02_CodeReview_report.md` — S02 review findings
- `ai-dev/work/F-00049/reports/F-00049_S03_API_report.md` — S03 report
- `ai-dev/work/F-00049/reports/F-00049_S04_CodeReview_report.md` — S04 review findings
- `ai-dev/work/F-00049/reports/F-00049_S05_Frontend_report.md` — S05 report
- `ai-dev/work/F-00049/reports/F-00049_S06_CodeReview_report.md` — S06 review findings
- All implementation files (read in full):
  - `orch/rag/qa.py`
  - `dashboard/routers/code_qa.py`
  - `dashboard/app.py`
  - `dashboard/templates/fragments/code_qa_panel.html`
  - `dashboard/templates/project_code.html`
  - `tests/unit/test_qa_engine.py`
  - `tests/integration/test_code_qa_routes.py`

## Output Files

- `ai-dev/work/F-00049/reports/F-00049_S07_CodeReview_Final_report.md` — Final review report

---

## Context

You are doing the **final cross-agent review** for **F-00049: Code Understanding Q&A Panel**. All three implementation agents (backend, API, frontend) have delivered their work. Your role is to verify the entire feature works cohesively end-to-end, that all acceptance criteria are met, that no regressions have been introduced, and that the code is ready for QV gates.

Read ALL input files before writing your findings.

---

## Review Checklist

### 1. End-to-End Coherence

- Does `QAEngine.answer_stream()` yield `str` tokens? Does the API endpoint consume these and wrap them in `data: {"token": "..."}\n\n`?
- Does the frontend `fetch()` SSE client parse `data: {"token": "..."}` lines and append to the assistant bubble?
- Does `"__ERROR__:..."` from the engine become `data: {"event": "error", "message": "..."}` in the API and trigger an error bubble in the UI?
- Does the `done` event carry `full_response` and does the frontend use it to populate `qaHistory`?
- Is the conversation history flow correct: JS sends `conversation_history`, API passes it to engine as list of dicts, engine truncates and converts to `ChatMessage` objects?

### 2. Contract Verification

Verify the request/response contract from the design document:

Request:
```json
{
  "question": "...",
  "context_level": "architecture|module",
  "context_doc_id": "...|null",
  "module_path": "...|null",
  "conversation_history": [{"role": "user|assistant", "content": "..."}]
}
```

Response SSE events:
```
data: {"token": "..."}      (repeated)
data: {"event": "done", "full_response": "..."}  (terminal success)
data: {"event": "error", "message": "..."}       (terminal error)
```

Are all fields mapped correctly between the three layers?

### 3. Acceptance Criteria Verification

Review each AC from the design document against the implementation:

- **AC1** (Token streaming): Does answer_stream yield tokens, API format them, frontend append them?
- **AC2** (Module filter): Does engine filter LanceDB by `module_path` when `context_level == "module"`?
- **AC3** (Architecture context): Does engine skip the filter when `context_level == "architecture"`?
- **AC4** (History truncation): Does `_truncate_history()` cap at `MAX_HISTORY_TURNS * 2 = 10`? Is it called?
- **AC5** (Ollama unavailable): Does the error propagate to an SSE error event? Does frontend show error bubble?
- **AC6** (Project not found): Does API return HTTP 404 before starting the stream?
- **AC7** (No index found): Does API return HTTP 404 with the right message?
- **AC8** (Input validation): Does Pydantic reject questions > 1000 chars with 422?
- **AC9** (UI collapse): Is the toggle implemented? Does it swap icon and label?
- **AC10** (Context label): Does `qaUpdateContextLabel()` read from `data-context-level` correctly?

### 4. Security Cross-Check

- Is all user-supplied text (question, streamed tokens) added via `.textContent` (not `.innerHTML`)?
- Is `QA_PROJECT_ID` injected safely via Jinja2 `{{ current_project.id }}` (not user-controlled)?
- Are there no open redirect or SSRF risks in the endpoint?
- Are there no hardcoded credentials in any file?

### 5. Open Issues from Prior Reviews

Read S02, S04, and S06 review reports. For each CRITICAL or HIGH finding:
- Was it fixed? If not, escalate it here with the same severity.
- For MEDIUM (fixable) findings that were marked as needing fix: was the fix applied?

Report any unresolved mandatory fixes as CRITICAL in this final review.

### 6. Test Coverage Gaps

- Are there integration tests for the SSE token streaming path?
- Are there unit tests for all three of: `_build_system_prompt()`, `_truncate_history()`, and `answer_stream()` error path?
- Is the missing-index-on-disk scenario tested?
- Are there any boundary scenarios from the design document that have no test coverage?

### 7. Regression Check

- Does `dashboard/app.py` still register ALL previously registered routers (none removed)?
- Does `project_code.html` still render the architecture panel and job status panel as before F-00049?
- Does `orch/rag/__init__.py` still export what it exported before (if it was modified)?

### 8. Code Quality Sweep

- No `from __future__ import annotations` missing from any new `.py` file?
- No `TYPE_CHECKING` guard missing for type-only imports?
- No hardcoded ports, model names, or index paths?
- No dead code, commented-out blocks, or TODO comments left in?
- No `print()` debug statements?

---

## Test Verification (NON-NEGOTIABLE)

Before submitting your final review:

1. Run: `uv run pytest tests/unit/ -v`
2. Run: `uv run pytest tests/integration/ -v --alluredir=allure-results`
3. Run: `uv run ruff check orch/rag/qa.py dashboard/routers/code_qa.py`
4. Run: `uv run mypy orch/rag/qa.py dashboard/routers/code_qa.py`
5. Report actual pass/fail counts

---

## Browser Verification (Required)

```bash
playwright-cli kill-all
playwright-cli open http://localhost:9900
# Navigate to a project Code tab
playwright-cli snapshot
# Check: Q&A panel visible at bottom
# Check: context label shows "Architecture"
# Check: input field and Ask button present
playwright-cli click "#qa-collapse-btn"
playwright-cli snapshot
# Check: panel is collapsed
```

---

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Feature broken, XSS, data loss, unresolved prior CRITICAL | Must fix before merge |
| **HIGH** | Major missing requirement, unresolved prior HIGH | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Improvement, not blocking | Optional |
| **LOW** | Minor style, nitpick | Informational |

---

## Final Review Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00049",
  "verdict": "pass|fail",
  "unresolved_prior_findings": [],
  "new_findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing|integration",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "ac_verified": {
    "AC1": "pass|fail",
    "AC2": "pass|fail",
    "AC3": "pass|fail",
    "AC4": "pass|fail",
    "AC5": "pass|fail",
    "AC6": "pass|fail",
    "AC7": "pass|fail",
    "AC8": "pass|fail",
    "AC9": "pass|fail",
    "AC10": "pass|fail"
  },
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "ready_for_qv_gates": true,
  "notes": ""
}
```

- `verdict`: `pass` only if ALL ACs pass AND zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `ready_for_qv_gates`: Set `true` only if `verdict == "pass"`.
