# CR-00064_S05_CodeReview_Final_prompt

**Work Item**: CR-00064 — Clear Chat History Button in AI Assistant
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item has no migrations. N/A.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00064 --json`
- `ai-dev/active/CR-00064/CR-00064_CR_Design.md`
- All step reports: `ai-dev/active/CR-00064/reports/CR-00064_S01_*`, `S02_*`, `S03_*`, `S04_*`
- All files in all implementation reports' `files_changed`

## Output Files

- `ai-dev/active/CR-00064/reports/CR-00064_S05_CodeReview_Final_report.md`

## Context

Final cross-agent review of the Clear Chat History button feature (CR-00064). Verify all 5 ACs are met and all cross-cutting concerns are addressed.

## Read the Design Document FIRST

Verify all ACs:
- AC1: Clear button visible, disabled when empty, enabled when history exists
- AC2: `window.confirm()` gate before destructive action
- AC3: Full clear pipeline end-to-end (API → DOM → system message → button disabled → new stream)
- AC4: Pi runtime path works
- AC5: SSE reconnects to new session; old `last-eid` cleared

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

### 1. Completeness

- All 5 ACs implemented?
- All test files named in TDD section present in `files_changed`?

### 2. Cross-Agent Consistency

- API endpoint response shape `{"tab": ...}` matches what frontend expects (`data.tab.opencode_session_id`)?
- ES5 style consistent throughout all JS changes?

### 3. Integration Points

- `_connectStream(tabId)` correctly picks up the new `opencode_session_id` from the updated `_tabs` array?
- The updated tab in `_tabs` has the new `opencode_session_id` before `_connectStream` is called?

### 4. Test Coverage

- Both runtime paths (OpenCode and Pi) tested in `test_chat_router.py`?
- Frontend button enabled/disabled state tested?
- SSE reset logic tested?

### 5. Architecture + Security

- No hardcoded credentials or URLs.
- `window.confirm()` is synchronous — no async gap between confirm and the destructive action.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/ -v -k "chat" --no-header
```

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "CR-00064",
  "steps_reviewed": ["S01", "S02", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
