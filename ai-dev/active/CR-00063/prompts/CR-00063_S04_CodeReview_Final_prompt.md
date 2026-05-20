# CR-00063_S04_CodeReview_Final_prompt

**Work Item**: CR-00063 — Restore Chat Message History on Browser Reload
**Review Step**: S04 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item has no migrations. N/A.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00063 --json`
- `ai-dev/active/CR-00063/CR-00063_CR_Design.md` — Design document
- All implementation step reports: `ai-dev/active/CR-00063/reports/CR-00063_S01_*_report.md`, `CR-00063_S03_*_report.md`
- All code review reports: `ai-dev/active/CR-00063/reports/CR-00063_S02_*_report.md`
- All files listed in all implementation reports' `files_changed`

## Output Files

- `ai-dev/active/CR-00063/reports/CR-00063_S04_CodeReview_Final_report.md` — Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for CR-00063 — Restore Chat Message History on Browser Reload.

## Read the Design Document FIRST

Read all `## Acceptance Criteria` and `## TDD Approach` sections. Every criterion is a mandatory check.

Verify all four ACs are satisfied:
- AC1: `_loadTabHistory` renders tool calls and tool results
- AC2: Non-200 responses and network errors show a user-visible error message
- AC3: `_bootstrapTabs` uses `last_active_at` for fallback tab selection when sessionStorage is cleared
- AC4: Text-only conversations still render correctly (no regression)

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

### 1. Completeness vs Design Document

- All four ACs implemented?
- `tests/dashboard/test_chat_history_restore.py` exists and covers AC1+AC2+AC3?
- `test_chat_panel_event_protocol.py` still passes?

### 2. Cross-Agent Consistency

- ES5 style consistent throughout?
- No new Tailwind class additions that bypass `make css`?

### 3. Integration Points

- `_appendToolCall` and `_appendToolResult` called with correct argument shapes from history loop?
- `_appendSystemMessage` called with `'error'` type for failures?

### 4. Test Coverage (Holistic)

- Both OpenCode and Pi runtime tool part type strings handled (`'tool-use'` and `'tool_use'`)?
- Error path (non-200 response) tested?
- Tab restore fallback (last_active_at sort) tested?

### 5. Architecture Compliance

- No silent error swallowing remains?
- No XSS: tool content escaped before DOM insertion?

### 6. Security (Cross-Cutting)

- Tool call/result content is HTML-escaped (uses existing `_escHtml` helper or equivalent)?

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/ -v -k "chat" --no-header
```

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview_Final",
  "work_item": "CR-00063",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
