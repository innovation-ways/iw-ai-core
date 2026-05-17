# I-00087_S04_CodeReview_Tests_prompt

**Work Item**: I-00087 — AI Assistant chat panel does not render model responses
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute any Docker container/volume/network management command. Allowed: testcontainers via pytest fixtures, read-only `docker ps/inspect/logs`, and `./ai-core.sh`/`make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade`, `alembic downgrade`, or `alembic stamp` against the live orchestration DB.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00087 --json`
- `ai-dev/active/I-00087/I-00087_Issue_Design.md`
- `ai-dev/active/I-00087/reports/I-00087_S03_Tests_report.md`
- `tests/dashboard/test_chat_panel_event_protocol.py` — the new test file
- `dashboard/static/chat_assistant/chat.js` — the file the tests pin
- `orch/chat/filters.py` — the constant the tests import
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — review against these rules

## Output Files

- `ai-dev/active/I-00087/reports/I-00087_S04_CodeReview_report.md` — review report

## Context

You are reviewing the test coverage added by S03 for I-00087. The bug was wire-protocol drift between `chat.js` and opencode; the tests pin the contract so it can't drift again silently.

## Read the Design Document FIRST

Read `ai-dev/active/I-00087/I-00087_Issue_Design.md` sections **Test to Reproduce**, **Acceptance Criteria**, and **TDD Approach**. Note:

- The design names exactly one test file: `tests/dashboard/test_chat_panel_event_protocol.py`. If S03's `files_changed` is missing this file → CRITICAL.
- AC5 requires the tests to have failed against the pre-S01 code. S03's `tdd_red_evidence` must record this — verify it is non-empty and looks plausible.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on S03's `files_changed`:

```bash
make lint
make format-check
```

NEW violations → CRITICAL with `category: "conventions"`.

## Review Checklist

### 1. Coverage of design's TDD Approach

Open the test file. Cross-check against the seven test names listed in S03's prompt:

- `test_chat_js_registers_every_interesting_event`
- `test_chat_js_reads_properties_delta_for_streaming_text`
- `test_chat_js_history_reads_info_and_parts`
- `test_chat_js_preserves_session_storage_key`
- `test_chat_js_passes_last_event_id_on_reconnect`
- `test_chat_js_listens_for_session_idle`
- `test_chat_js_distinguishes_properties_from_data`

Missing tests → HIGH. Renamed but semantically equivalent → MEDIUM_FIXABLE if the new name is misleading; LOW if it is clearly equivalent.

### 2. Assertion strength (PRIMARY FOCUS — I003 lesson)

For EVERY test in the file, ask the mutation question: "Would this assertion fail if the bug came back?"

- `assert set(INTERESTING_EVENTS).issubset(registered)` → strong (specific contract).
- `assert "properties.delta" in js` → strong (specific accessor).
- `assert "info" in body` → weak (`"info"` is a substring of `"information"`, `"infos"`, comments, etc.). Demand `.info` or a regex with word boundaries. MEDIUM_FIXABLE.
- `assert len(registered) > 0` → very weak. CRITICAL — this is exactly the I003 failure mode.
- `assert chat_js_contents` (truthy file content check) → useless. CRITICAL.

### 3. RED evidence

S03's `tdd_red_evidence` field MUST contain:
- A test ID from this file (expected: `test_starter_listener_set_would_have_failed_protocol_check`).
- The specific `missing` set that the pre-fix listener literal failed against (e.g., `{'message.part.updated', 'permission.replied', ...}`) — NOT just `"AssertionError"` with no payload.
- A confirmation sentence that the post-S01 `chat.js` passes the live contract test.

If the field uses `"n/a"` — fail the review HIGH. This is a `tests-impl` step; absence of RED evidence is unacceptable.

If S03's RED procedure shows ANY runtime mutation of `chat.js` (`git checkout`, `git stash`, `git show ... > path`, file copy over shipped source, etc.) — that's a CRITICAL finding. Pre-fix reproduction must be a design-time / in-test-fixture exercise; reverting shipped source at runtime is a banned anti-pattern (causes timeouts and downstream gate failures).

If the snippet looks like an `ImportError`, `SyntaxError`, fixture error, or collection error — it's not a real RED (the test itself is broken, not the production code). HIGH finding.

### 4. Test isolation

- The tests read `chat.js` from disk. There is no DB, no FastAPI client, no testcontainer required. If S03 added unnecessary fixtures (`db_session`, `client`, `pg_engine`), that's MEDIUM_FIXABLE — collection time penalty.
- The tests must be deterministic. Reading a file is deterministic; verify there's no randomness, no time-dependent logic, no network call.

### 5. Run the tests yourself

```bash
uv run pytest tests/dashboard/test_chat_panel_event_protocol.py -v --no-cov
```

All tests must pass green. If any fail, that's a CRITICAL — the test suite would block merge.

Also confirm no regression elsewhere:

```bash
uv run pytest tests/dashboard/test_chat_router.py tests/unit/test_chat_client.py -v --no-cov
```

Should still be 52 passed.

### 6. Scope discipline

S03 must NOT have modified `chat.js`, `orch/chat/filters.py`, or any production code. If `files_changed` includes a production file → CRITICAL.

### 5a. TDD RED Evidence — Required for this `tests-impl` step

S03 is a `tests-impl` step. RED evidence is mandatory per Section 3 above; treat the absence as HIGH.

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
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00087",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "tests/dashboard/test_chat_panel_event_protocol.py",
      "line": 0,
      "description": "",
      "suggestion": ""
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "7 passed, 0 failed",
  "notes": ""
}
```
