# CR-00063_S02_CodeReview_prompt

**Work Item**: CR-00063 — Restore Chat Message History on Browser Reload
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item has no migrations. N/A.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00063 --json`
- `ai-dev/active/CR-00063/CR-00063_CR_Design.md` — Design document
- `ai-dev/active/CR-00063/reports/CR-00063_S01_Frontend_report.md` — S01 implementation report
- All files listed in S01 report's `files_changed`

## Output Files

- `ai-dev/active/CR-00063/reports/CR-00063_S02_CodeReview_report.md` — Review report

## Context

You are reviewing the frontend-impl work done in S01 for CR-00063 — fixing `_loadTabHistory` to render all message types and replacing the silent catch.

Read the design document to understand what was intended. Read the S01 report to understand what was done. Then review all changed files.

## Read the Design Document FIRST

Read `## Acceptance Criteria` and `## TDD Approach` in full before opening any code.

Key things to verify against the design:

- AC1: Does `_loadTabHistory` now render tool call and tool result messages in addition to user/assistant text?
- AC2: Is the silent `.catch` replaced with a user-visible `_appendSystemMessage` call?
- AC3: Does `_bootstrapTabs` use `last_active_at` for fallback tab selection?
- AC4: Are text-only conversations still rendered correctly (no regression)?
- TDD: Is `tests/dashboard/test_chat_history_restore.py` present in `files_changed`?

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

If either reports new violations in the changed files, classify each as a **CRITICAL** finding.

## Review Checklist

### 1. Architecture Compliance

- JS code is vanilla ES5 (no arrow functions, no `const`/`let`, no template literals) — match existing `chat.js` style.
- New rendering logic reuses `_appendToolCall` and `_appendToolResult` helpers rather than duplicating them.
- Error messages use `_appendSystemMessage(text, 'error')`, not custom DOM manipulation.

### 2. Code Quality

- `_loadTabHistory` iterates over all `parts` of each message and dispatches on `part.type`.
- Both `'tool-use'` and `'tool_use'` part type strings are handled (OpenCode vs Pi runtime difference).
- The non-OK response guard (`if (!r.ok)`) throws an error that flows into the `.catch` handler.
- No silent error suppression remains.
- The `last_active_at` fallback in `_bootstrapTabs` handles the case where `last_active_at` is null/undefined (tabs without timestamps should not crash the sort).

### 3. Project Conventions

- ES5 only — no arrow functions, no `const`/`let`.
- Plain CSS added to `dashboard/static/chat_assistant/chat.css` if needed, NOT via Tailwind `make css`.
- `make lint` includes `node --check` — verify the JS is parseable.

### 4. Security

- No XSS: tool call/result content must be escaped before inserting into the DOM. Check that `_appendToolCall` and `_appendToolResult` already escape content, or that the new code does.
- No eval or dynamic script injection.

### 5. Testing

- `tests/dashboard/test_chat_history_restore.py` is present in `files_changed`.
- Tests assert: `_appendToolCall` wired in `_loadTabHistory`; `_appendToolResult` wired in `_loadTabHistory`; `silently ignore` removed; `last_active_at` present in `_bootstrapTabs`.
- `tests/dashboard/test_chat_panel_event_protocol.py` still passes (no `_loadTabHistory` regression).
- `tdd_red_evidence` is present and plausible in the S01 report.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_chat_history_restore.py tests/dashboard/test_chat_panel_event_protocol.py -v
```

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, security vulnerability, lint failure |
| **HIGH** | Missing AC, architectural violation |
| **MEDIUM (fixable)** | Convention violation, missing edge case |
| **MEDIUM (suggestion)** | Design improvement |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00063",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
