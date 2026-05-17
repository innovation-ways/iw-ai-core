# I-00087_S03_Tests_prompt

**Work Item**: I-00087 — AI Assistant chat panel does not render model responses
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any Docker container/volume/network management command. Allowed: testcontainers via pytest fixtures, read-only `docker ps/inspect/logs`, and `./ai-core.sh`/`make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade`, `alembic downgrade`, or `alembic stamp` against the live orchestration DB. This step does not involve migrations.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00087 --json`
- `ai-dev/active/I-00087/I-00087_Issue_Design.md` — read sections **Test to Reproduce** and **TDD Approach** in full
- `ai-dev/active/I-00087/reports/I-00087_S01_Frontend_report.md` — confirms what S01 changed
- `dashboard/static/chat_assistant/chat.js` — the file under test
- `orch/chat/filters.py` — your tests pin to `INTERESTING_EVENTS`
- `tests/dashboard/test_chat_router.py` — example test style and conftest behaviour
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — MANDATORY reading before writing tests

## Output Files

- `ai-dev/active/I-00087/reports/I-00087_S03_Tests_report.md` — step report
- `tests/dashboard/test_chat_panel_event_protocol.py` — new test file

## Context

You are adding regression tests that pin the chat panel's wire-protocol contract to opencode. The S01 step already fixed the production code. Your job:

1. Write a reproduction test (or set) that would FAIL against pre-S01 `chat.js` and PASSES against the current code.
2. Write additional regression tests covering the session-continuity invariants and payload extraction.
3. Capture RED evidence — record in your report a snippet from running the test against the pre-S01 version of `chat.js`.

## Requirements

### 1. Create `tests/dashboard/test_chat_panel_event_protocol.py`

Implement at least these test functions (based on the **TDD Approach** section of the design doc):

| Test name | What it asserts |
|---|---|
| `test_chat_js_registers_every_interesting_event` | Set-subtract `INTERESTING_EVENTS - registered_event_names_from_chat_js` is empty. |
| `test_chat_js_reads_properties_delta_for_streaming_text` | `chat.js` contains both `properties.delta` and `properties.part` (handler reads opencode wire shape). |
| `test_chat_js_history_reads_info_and_parts` | The `_loadHistory` function body contains `.info` and `.parts` accessors (history-shape regression). |
| `test_chat_js_preserves_session_storage_key` | The literal `'iw-chat-session-' + _tabId` still appears (session-continuity invariant). |
| `test_chat_js_passes_last_event_id_on_reconnect` | `last_event_id=` URL fragment still appended (replay-after-blip invariant). |
| `test_chat_js_listens_for_session_idle` | `session.idle` is still in the registered set (regression for the one event that already worked). |
| `test_chat_js_distinguishes_properties_from_data` | Handler source contains BOTH `properties.` and `data.` reads (relay-synthesised events `gap`/`reconnecting` still work). |

The starter implementations in the design doc's **Test to Reproduce** section are good — use them as a baseline. Strengthen if you spot weak assertions.

### 2. Test file conventions

- Place the file at **`tests/dashboard/test_chat_panel_event_protocol.py`** (NOT `tests/unit/` — the `client` fixture lives in `tests/dashboard/conftest.py` per the gotcha in `tests/CLAUDE.md`, even though this test doesn't use it). Future tests in the same file may need it; keep it discoverable.
- Use `from pathlib import Path` and resolve `chat.js` relative to `__file__` so the test works in any worktree:
  ```python
  CHAT_JS = Path(__file__).resolve().parents[2] / "dashboard/static/chat_assistant/chat.js"
  ```
- Import `INTERESTING_EVENTS` from `orch.chat.filters` so a future addition to the backend constant automatically forces the frontend to register the new event:
  ```python
  from orch.chat.filters import INTERESTING_EVENTS
  ```
- Use plain Python — no Jest/Vitest, no Node subprocess. The contract checks are pure text/AST inspection of `chat.js`.

### 3. Assertion strength (NON-NEGOTIABLE — I003 lesson)

Per `tests/CLAUDE.md` §0 ("the mutation test question"): every assertion must be one that would fail if the production code regressed. Apply this rigorously:

- ✗ BAD: `assert len(registered) > 0` (passes even if `chat.js` registers a single irrelevant event)
- ✓ GOOD: `assert set(INTERESTING_EVENTS).issubset(registered)` with a `missing = ...` subtraction in the failure message
- ✗ BAD: `assert "properties" in js` (passes if `properties` appears in any comment or string)
- ✓ GOOD: `assert "properties.delta" in js and "properties.part" in js` (specific accessors required by the wire shape)

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

In this work item, the equivalent of "specific value" is: the **set of event names** must include every member of `INTERESTING_EVENTS`, and the source must contain the **specific accessors** `properties.delta`, `properties.part`, `.info`, `.parts`.

### 4. RED evidence

Capture the failing run via an **in-test fixture string** — DO NOT modify, revert,
`git checkout`, `git stash`, or otherwise touch `chat.js` at runtime. The
production file has already been fixed by S01 and must stay fixed for the
remainder of the workflow (subsequent QV gates run against it). Reverting
shipped source at runtime to "prove RED" is an anti-pattern that has caused
multi-thousand-second timeouts in past items.

Instead, define a `PRE_FIX_NAMED_EVENTS` literal in the test file that
captures the pre-S01 array contents (a Python `frozenset` containing exactly
the strings that lived in `chat.js`'s `namedEvents` array before the fix:
`'message.part', 'message.snapshot', 'message.complete', 'message.updated',
'tool.call', 'tool.result', 'permission.asked', 'session.idle', 'error',
'gap', 'reconnecting'`). Add one extra test
`test_starter_listener_set_would_have_failed_protocol_check` that runs the
same protocol-check logic against the literal and asserts the
`INTERESTING_EVENTS - PRE_FIX_NAMED_EVENTS` set is non-empty (i.e. the pre-fix
listener set would have failed the contract test). That assertion IS the RED
evidence — capture its output (when the test is intentionally inverted, or
via a `print(missing)` call recorded in the report).

The `tdd_red_evidence` field in your report must include:
- Test ID (`tests/dashboard/test_chat_panel_event_protocol.py::test_starter_listener_set_would_have_failed_protocol_check`)
- The exact `missing` set the inverted check produced (e.g.,
  `{'message.part.updated', 'permission.replied', 'session.updated', 'session.error', 'tool.execute.before', 'tool.execute.after'}`)
- One short sentence confirming the post-S01 contract test passes against
  the live `chat.js`

### 5. Run ONLY the new test file

Per `tests/CLAUDE.md` and the I-00073 lesson, do NOT run `make test-integration` or `make test-unit` in this step. Run only:

```bash
uv run pytest tests/dashboard/test_chat_panel_event_protocol.py -v --no-cov
```

Confirm all your new tests pass against the current (post-S01) code, then report.

### 6. Out of scope (do NOT do these)

- Do NOT add Jest, Vitest, or any JS test framework.
- Do NOT modify `chat.js`, `orch/chat/filters.py`, or any production file. You are writing tests, not fixing code.
- Do NOT add new opencode-spike or fake-opencode harnesses — the protocol pin is sufficient and proportional.

## Project Conventions

Read `CLAUDE.md`, `tests/CLAUDE.md`, and `skills/iw-ai-core-testing/SKILL.md`. Key rules:
- NEVER connect tests to live DB (port 5433). Your test reads `chat.js` from disk; no DB involved.
- NEVER call `importlib.reload(orch.config)` — not relevant here.
- Tests must be deterministic — your tests are file-content checks, so determinism is automatic.

## TDD Requirement

The reproduction logic IS the test — there is no "implementation" beyond the tests themselves. RED evidence is required per Section 4 above.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

```bash
make format       # auto-fix formatting
make typecheck    # zero errors on your new file
make lint         # zero errors
```

Populate `preflight` in the result contract.

## Test Verification (NON-NEGOTIABLE)

Run only the new file:

```bash
uv run pytest tests/dashboard/test_chat_panel_event_protocol.py -v --no-cov
```

Do not run `make test-integration` or `make test-unit` — those are S09 / S10.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00087",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_chat_panel_event_protocol.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "7 passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_chat_panel_event_protocol.py::test_starter_listener_set_would_have_failed_protocol_check — in-test fixture: PRE_FIX_NAMED_EVENTS missed {'message.part.updated', 'permission.replied', 'session.updated', 'session.error', 'tool.execute.before', 'tool.execute.after'}; post-S01 chat.js passes the contract test (RED proven without touching shipped source).",
  "blockers": [],
  "notes": ""
}
```
