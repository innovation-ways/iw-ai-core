# I-00087_S05_CodeReview_Final_prompt

**Work Item**: I-00087 — AI Assistant chat panel does not render model responses
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT execute any Docker container/volume/network management command. Allowed: testcontainers via pytest fixtures, read-only `docker ps/inspect/logs`, and `./ai-core.sh`/`make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade`, `alembic downgrade`, or `alembic stamp` against the live orchestration DB. This work item does not involve migrations.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00087 --json`
- `ai-dev/active/I-00087/I-00087_Issue_Design.md`
- `ai-dev/active/I-00087/I-00087_Functional.md`
- All implementation step reports: `ai-dev/active/I-00087/reports/I-00087_S0[1-4]_*_report.md`
- All files listed in implementation reports' `files_changed`:
  - `dashboard/static/chat_assistant/chat.js`
  - `tests/dashboard/test_chat_panel_event_protocol.py`
- `orch/chat/filters.py` and `.opencode/node_modules/@opencode-ai/sdk/dist/gen/types.gen.d.ts` for cross-checking the contract

## Output Files

- `ai-dev/active/I-00087/reports/I-00087_S05_CodeReview_Final_report.md`

## Context

You are the final cross-agent reviewer for I-00087. The previous reviews (S02, S04) checked S01 and S03 in isolation. Your job is to check that the implementation and tests together actually satisfy the design, and that no cross-step gap was missed.

## Read the Design Document FIRST

Read `ai-dev/active/I-00087/I-00087_Issue_Design.md` in full. Pay extra attention to:

- **Acceptance Criteria** (AC1..AC6) — every criterion is a mandatory check.
- **Session continuity invariants** — explicitly listed; the implementation MUST preserve all six.
- **Concrete event handling table** — every row is a deliverable.
- **TDD Approach** — the test file name and contents are pinned.

Also read `ai-dev/active/I-00087/I-00087_Functional.md` and confirm the human-facing description matches what the code does.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations in any file from any step's `files_changed` → CRITICAL.

## Cross-Agent Review Checklist

### 1. AC traceability matrix

Build (or update) a small table mapping each AC to the file/test that demonstrates it:

| AC | Demonstrated by |
|---|---|
| AC1 (streaming) | `chat.js:_handleEvent` handles `message.part.updated`; test `test_chat_js_reads_properties_delta_for_streaming_text` |
| AC2 (history reload) | `chat.js:_loadHistory` rewrite; test `test_chat_js_history_reads_info_and_parts` |
| AC3 (tool calls) | `chat.js:_handleEvent` handles `tool.execute.before/after`; covered by AC1's listener test indirectly |
| AC4 (permissions) | `chat.js:_handleEvent` handles `permission.updated`; covered by `test_chat_js_registers_every_interesting_event` |
| AC5 (regression tests) | All seven tests in `test_chat_panel_event_protocol.py` |
| AC6 (browser verification) | S11 (qv-browser) — runs separately, not your scope but record that the prompt exists |

If any AC has no demonstrator → HIGH.

### 2. Cross-file consistency

- The set of names registered in `chat.js` MUST equal (or be a superset of) `INTERESTING_EVENTS` in `orch/chat/filters.py`. The test `test_chat_js_registers_every_interesting_event` enforces this; verify the test would actually catch a divergence (mutation question).
- The accessors `chat.js` uses (`properties.delta`, `properties.part`, `.info`, `.parts`) MUST match what `tests/dashboard/test_chat_panel_event_protocol.py` asserts exists. If S01 used `properties["delta"]` (bracket form) but S03 asserts `properties.delta` (dot form) by string match — that's a HIGH (test passes only by coincidence).

### 3. Distrust "no production code change needed"

Per the meta-review instructions: when the implementation introduces new event types or new shapes the rest of the codebase has not seen, re-trace the whole path. For this item:

- `_appendOrUpdateAssistantMessage` is now called with `info.id` (a `msg_*` string) where before it was called with the SSE `lastEventId` (an `evt_*` string). Verify that the dedup logic inside `_appendOrUpdateAssistantMessage` does not assume the prefix or format. If it does, this is a latent crash — HIGH.
- `_seenIds` (the client-side dedup map) keys on `lastEventId`. If S01 changed how `_handleEvent` resolves `eid` (e.g., switched from `e.lastEventId` to a derived value from `properties`), the dedup may silently fail-open. Inspect carefully.

### 4. Session-continuity audit (user-stated requirement)

The user explicitly required: "when the user interacts with the LLM it keeps the same session and context." Re-run a focused grep on `chat.js` to confirm the six invariants are still present (the S01 report should already have this, but the final reviewer verifies independently):

```bash
grep -nE "'iw-chat-session-' \+ _tabId|last_event_id=|_loadHistory\(|sessionStorage\.removeItem|switchSession|chat-assistant-chip" dashboard/static/chat_assistant/chat.js
```

All six markers MUST appear at least once. Missing → HIGH (user-stated requirement violation).

### 5. Test cohesion

- All seven new tests should pass.
- No existing test should regress. Run:
  ```bash
  uv run pytest tests/dashboard/test_chat_router.py tests/unit/test_chat_client.py tests/dashboard/test_chat_panel_event_protocol.py -v --no-cov
  ```
  Expected: 59 passed (52 existing + 7 new).
- If S03 added more than seven tests, that's fine — count them and confirm all pass.

### 6. Project conventions

Re-read `dashboard/CLAUDE.md`:
- The clipboard helper convention still applies (not relevant here — no clipboard buttons added).
- The `make css` rule: if S01 added any new CSS class to chat.js but did not append a rule to `dashboard/static/styles.css` (or trigger Tailwind), that class will not render. CRITICAL if the tool-execute bubble depends on a class the file does not define.

### 7. Security & dependencies

- No new npm dependencies (this project ships pure-JS chat.js).
- All user-controlled text rendered into the DOM goes through `_escHtml` — if S01 added a `tool.execute.before` renderer that does string concatenation into `innerHTML` without `_escHtml`, that's CRITICAL (XSS risk if a tool name contained HTML).

### 8. Functional doc alignment

Read `I-00087_Functional.md` and confirm the actual behaviour matches each "What Changed" bullet. Drift → MEDIUM_FIXABLE (update the functional doc, not the code).

## Test Verification (NON-NEGOTIABLE)

Run the focused test suite:

```bash
uv run pytest tests/dashboard/test_chat_router.py tests/unit/test_chat_client.py tests/dashboard/test_chat_panel_event_protocol.py -v --no-cov
```

Report test results accurately. Do NOT run `make test-integration` or `make test-unit` here — the QV gates own those.

## Severity Levels

| Severity | Meaning | Action Required |
|---|---|---|
| **CRITICAL** | Breaks functionality, data loss, security | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00087",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing|cross_step",
      "file": "",
      "line": 0,
      "description": "",
      "suggestion": ""
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "59 passed, 0 failed",
  "notes": "AC traceability matrix completed; all six session-continuity invariants present."
}
```
