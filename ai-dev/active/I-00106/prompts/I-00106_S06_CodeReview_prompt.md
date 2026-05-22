# I00106_S06_CodeReview_prompt

**Work Item**: I-00106 -- Agent Session Log modal renders oldest-first — newest activity buried at the bottom
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed exceptions: testcontainer fixtures, read-only `docker ps`/`docker logs`/`docker inspect`,
and `./ai-core.sh` / `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This work item adds NO migration. Flag any alembic file as a scope violation.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00106 --json` for the current step list.
- `ai-dev/active/I-00106/I-00106_Issue_Design.md` -- Design document (read §Test to Reproduce, §TDD Approach, AC1–AC5).
- `ai-dev/active/I-00106/reports/I-00106_S05_Tests_report.md` -- S05 implementation report.
- `tests/unit/test_session_reader.py` -- Unit tests appended by S05.
- `tests/dashboard/test_session_log_modal_ordering.py` -- Reproduction + render-order tests created by S05.
- `orch/daemon/session_reader.py` and `dashboard/routers/items.py` -- The product code the tests exercise.

## Output Files

- `ai-dev/active/I-00106/reports/I-00106_S06_CodeReview_report.md` -- Review report.

## Context

You are reviewing the S05 test work for **I-00106**. S05 wrote a reproduction test for the
Agent Session Log modal render order plus regression tests for the turn-grouping helper.

Read the design document first — §Test to Reproduce, §TDD Approach (which names every test), and
Acceptance Criteria AC1–AC5. Cross-check every test the design names by path against the S05
report's `files_changed`. **If the design names a test that is missing, that is a CRITICAL finding.**

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading code, run on the changed test files. Report only — fix nothing.

```bash
make lint
make format-check
```

Any NEW violation in a changed file is a **CRITICAL** finding. If a command is unavailable, STOP
and raise a blocker.

## Review Checklist

### 1. Semantic correctness — NOT shape checking (primary focus)

The I-00106 bug is purely about **order**. A test that only checks counts or presence
(`len(turns) == 2`, `"segment" in html`) would pass against the **buggy** code and is worthless.
Every test MUST assert concrete **ordering**:

- The reproduction test asserts `html.index("NEWEST_TURN_MARKER") < html.index("OLDEST_TURN_MARKER")`
  (or an equivalent concrete position check), not merely that both markers exist.
- The within-turn-order test asserts the **exact** segment-type sequence
  `["thinking", "tool_call", "tool_result", "assistant"]`, not just the turn's length.
- The reverse-order test asserts the **newest** turn is at index 0 by checking a specific marker,
  not just that there are N turns.

Flag any test whose assertions would still pass if the helper returned the segments in the
ORIGINAL chronological order — that is a HIGH finding (a test that does not actually test the fix).

### 2. Coverage vs the design's TDD Approach

Confirm all named tests exist and target what the design says:

- `tests/dashboard/test_session_log_modal_ordering.py`:
  `test_i00106_session_log_modal_renders_newest_turn_first`,
  `test_session_log_modal_empty_state_still_renders`.
- `tests/unit/test_session_reader.py` (appended): the eight `test_group_turns_*` tests covering
  turn reversal, within-turn order, in-progress trailing turn, compaction, error termination,
  consecutive-assistant grouping, log-segment line reversal + purity, and empty input.

A missing named test is CRITICAL.

### 3. Test correctness and placement

- The reproduction test is under `tests/dashboard/` and uses a **file-local** `client` fixture
  (copied from `tests/dashboard/test_items_session_log.py` — there is no shared `client` in
  `conftest.py`) backed by the `db_session` testcontainer fixture that `tests/dashboard/conftest.py`
  re-exports; placement under `tests/dashboard/` is what makes that DB fixture resolvable (I-00067).
- The unit tests are pure (synthetic segment lists, no DB/files) and live in
  `tests/unit/test_session_reader.py`.
- The reproduction test genuinely exercises the `item_session_log` route end-to-end, not just the
  helper in isolation.
- The `log`-segment test also asserts input is not mutated (purity).
- Tests are isolated and deterministic — no reliance on the live DB (port 5433), no ordering
  dependence between tests.

### 4. Scope discipline

- The ONLY files changed must be `tests/unit/test_session_reader.py` and
  `tests/dashboard/test_session_log_modal_ordering.py`. Any product-code change in this step
  (`session_reader.py`, `items.py`, the template) is a scope violation — CRITICAL.
- Existing tests in `tests/unit/test_session_reader.py` must be untouched (only appended to).

## Test Verification (NON-NEGOTIABLE)

Run the new/modified test files and confirm they pass:

```bash
uv run pytest tests/unit/test_session_reader.py -v 2>&1 | tail -40
uv run pytest tests/dashboard/test_session_log_modal_ordering.py -v 2>&1 | tail -40
```

Report results accurately.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Missing required test, scope violation, security issue |
| **HIGH** | Test that does not actually test the fix (shape-only), significant gap |
| **MEDIUM (fixable)** | Weak assertion, missed edge case, convention violation |
| **MEDIUM (suggestion)** | Optional improvement |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00106",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 0,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL, zero HIGH, and zero MEDIUM (fixable) findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM (fixable).
