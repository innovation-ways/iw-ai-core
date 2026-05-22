# I-00105_S09_Tests_prompt

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S09
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Do NOT run any command that changes Docker container/volume/network state.
Testcontainers via pytest fixtures are the only exception. STOP and raise a
blocker if your task seems to need a prohibited command. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds **no migration**. If your work appears to need one, STOP and
raise a blocker.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00105 --json`.
- `ai-dev/work/I-00105/I-00105_Issue_Design.md` — design document (read §Test to Reproduce, §Acceptance Criteria, §TDD Approach).
- All prior step reports: `ai-dev/work/I-00105/reports/I-00105_S01..S07_*_report.md`, and the files listed in their `files_changed`.
- `orch/chat/context_usage.py` (S03's effective-budget meter), `orch/db/models.py` (`max_output_tokens`), the executor cap + overflow-detection helpers (S07), `tests/integration/conftest.py` (fixtures), `tests/CLAUDE.md`.

## Output Files

- `tests/unit/...`, `tests/integration/...` — new test files (see Requirements for placement rules)
- `ai-dev/work/I-00105/reports/I-00105_S09_Tests_report.md` — step report.

## Context

You are writing the reproduction test and the regression net for I-00105. Some
reproduction coverage may already exist from S03's TDD — your job is to make the
coverage complete and durable, not to duplicate.

### CRITICAL: Semantic correctness over shape checking

Tests must verify **specific expected values**, not just response shape:

- BAD: `assert pct is not None` / `assert isinstance(pct, float)` (shape only)
- GOOD: `assert pct >= 100.0` (semantic — a 131K-input MiniMax-M2.7 step is past the effective ceiling)
- GOOD: `assert spill_file.read_text() == original_output` (semantic — the spill preserved the full content exactly)

A test that only checks a value was returned does NOT prove the bug is fixed.

## Requirements

### 1. Reproduction test (AC1, AC3)

`test_i_00105_context_pct_accounts_for_output_reservation` — the design doc's
§Test to Reproduce gives the exact behavioural assertion. It MUST fail against
the pre-fix meter (raw-window division) and pass against the effective-budget
meter. Pure computation → `tests/unit/`.

### 2. Effective-budget meter regression tests (AC1)

- A model with a large `max_output_tokens` (MiniMax-M2.7: 204,800 / 131,072):
  input near the effective ceiling reports ≥100%.
- A model with a small `max_output_tokens` relative to its window: the
  percentage is close to the raw-window percentage.
- `max_output_tokens` is `None` → the meter falls back to raw-window behaviour
  and does not raise.
- The `safety_buffer` is subtracted (assert the exact percentage shifts by the
  expected amount when the buffer changes).

### 3. Migration / schema regression test (AC3)

An integration test (testcontainer `db_session`) asserting `agent_runtime_options`
has a `max_output_tokens` column and that the migration's backfill set the
`pi`/MiniMax-M2.7 row to `131072`.

### 4. Executor cap-helper regression tests (AC2)

If S07 produced a unit-testable cap/spill helper, cover it: oversized output →
a spill file is created containing the **full** original content, and the
returned preview includes head + tail + the file path; under-cap output →
returned unchanged. If S07's cap is pure shell with no testable surface, note
that in your report and cover what is reachable.

### 5. Executor overflow-detection regression tests (AC4)

S07 adds a context-overflow-detection helper. Cover it: runtime output that
contains an overflow signature (`context window exceeds limit` /
`context_length_exceeded` / an `invalid_request_error` carrying a
context-length message) → detected, returning a clear blocker message; clean
runtime output → **not** detected. Assert the specific blocker text and the
boolean/Optional result, not shape. If S07's detection is pure shell with no
unit-testable surface, note that in your report and cover what is reachable.

### 6. Placement rules

Per `tests/CLAUDE.md`: pure-Python no-I/O tests → `tests/unit/`; testcontainer
DB tests → `tests/integration/`; FastAPI/template tests via the `client`
fixture → `tests/dashboard/`. Tests must be order-independent (`pytest-randomly`
is on by default).

## Project Conventions

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` (MUST-read:
assertion-strength rules, the live-DB guard, testcontainer rules). Never connect
tests to the live DB (port 5433).

## TDD Note

This is a dedicated test-coverage step. Where a test reproduces the bug, verify
it genuinely fails against pre-fix logic by reasoning about the assertion (the
reproduction test would pass trivially if the meter still divided by the raw
window — confirm it does not). Do NOT `git checkout`/`git stash` to revert
source files at runtime.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`  2. `make typecheck`  3. `make lint`
4. `make test-assertions` — your new tests must not trip the assertion scanner (no no-assert / tautology / mock-only / bare `pytest.raises`).

## Test Verification (NON-NEGOTIABLE)

Run **only the test files you wrote** — do NOT run `make test-unit` or
`make test-integration` (those are QV gates S16/S17):
```bash
uv run pytest tests/unit/<your file> tests/integration/<your file> -v
```
Do not report `tests_passed: true` unless they all pass.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "tests-impl",
  "work_item": "I-00105",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — dedicated test-coverage step",
  "blockers": [],
  "notes": "Test files created and what each covers; any S07 cap surface that was not unit-testable."
}
```

## Lifecycle Commands

Start: `uv run iw step-start I-00105 --step S09`
On success: write the report, then
`uv run iw step-done I-00105 --step S09 --report ai-dev/work/I-00105/reports/I-00105_S09_Tests_report.md`
On failure: `uv run iw step-fail I-00105 --step S09 --reason "<brief reason>"`
You MUST call `step-done` (with `--report`) or `step-fail` before exiting.
