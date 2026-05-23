# I-00105_S03_Backend_prompt

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Do NOT run any command that changes Docker container/volume/network state.
Testcontainers via pytest fixtures are the only exception; read-only
`docker ps|inspect|logs` and `./ai-core.sh` / `make` targets are allowed. If
your task seems to need a prohibited command, STOP and raise a blocker. Full
policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds **no migration** — S01 already added `max_output_tokens`. You
MUST NOT create or apply a migration. If your work appears to need one, STOP
and raise a blocker.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00105 --json`.
- `ai-dev/work/I-00105/I-00105_Issue_Design.md` — design document (read §Root Cause Analysis, §Test to Reproduce, §Acceptance Criteria in full).
- `ai-dev/work/I-00105/reports/I-00105_S01_Database_report.md` — S01 report (the new column).
- `docs/research/R-00078-agent-tool-output-context-capping.md` — **MUST read** — the effective-budget formula is finding "A model's effective input budget is `window − max_output`".
- `orch/chat/context_usage.py` — the meter. `compute_context_pct()` near line 70; the raw-window division is at line 149 (`pct = (used_tokens / context_window) * 100.0`); `lookup_context_window()` near line 159.
- `orch/db/models.py` — `agent_runtime_options` now carries `context_window_tokens` and `max_output_tokens`.

## Output Files

- `orch/chat/context_usage.py` (modified)
- `tests/unit/...` — the reproduction test (see below)
- `ai-dev/work/I-00105/reports/I-00105_S03_Backend_report.md` — step report.

## Context

You are implementing the **effective-budget meter** — the core fix for AC1. The
gauge today divides used tokens by the *full* context window, so a model whose
output reservation is a large fraction of its window (MiniMax-M2.7: 131,072
output / 204,800 window) reads ~64% when it is actually at its ceiling.

## Requirements

### 1. Compute usage against the effective budget

Add a function to `orch/chat/context_usage.py` — e.g.
`compute_effective_context_pct(used_tokens, context_window, max_output_tokens, safety_buffer=...)`
— that computes the percentage against the **effective budget**:

```
effective_budget = context_window − max_output_tokens − safety_buffer
pct = (used_tokens / effective_budget) * 100.0
```

- `safety_buffer` — a small reserve (R-00078 cites opencode's 20,000-token
  buffer; pick a sensible default, expose it so it can be tuned).
- **`max_output_tokens` is `None`** → fall back to today's behaviour: divide by
  the raw `context_window` (degrade gracefully, never crash). This is required
  by AC and the design's Notes.
- Clamp the result to `[0, 100]`-or-higher consistently with the existing
  `compute_context_pct` contract — but the percentage MUST be allowed to reach
  and exceed 100 when input is past the effective ceiling (AC1).
- Keep the existing `compute_context_pct` working (other callers); add the new
  function rather than silently changing the old signature, unless you can
  update every caller cleanly within scope.

### 2. Resolve `max_output_tokens` for a runtime

Extend the lookup path (alongside `lookup_context_window`) so callers can obtain
`max_output_tokens` from the `agent_runtime_options` row. Keep it pure /
testable — the dashboard wiring is S05's job.

### 3. Reproduction test (TDD — RED first)

Write `test_i_00105_context_pct_accounts_for_output_reservation` (see the design
doc's §Test to Reproduce for the exact behavioural assertion). Place it in
`tests/unit/` (pure computation, no DB). **Run it RED first** against the
unmodified meter — confirm it fails because the meter has no output reservation
— capture the failure line. Then implement until GREEN.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. `orch/chat/context_usage.py` is "pure
helpers" — keep the new function pure (no DB calls inside the computation;
resolution of the row is a separate, thin function). Match the existing
docstring and type-annotation style.

## TDD Requirement

RED → GREEN → REFACTOR. Write the failing test first, run it targeted
(`uv run pytest tests/unit/.../test_x.py -v`), confirm it fails for the right
reason (an `AssertionError` from the missing reservation, not an `ImportError`),
capture the RED line, then implement.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting complete, run in order and fix anything reported:
1. `make format`  2. `make typecheck` (zero errors in files you touched)  3. `make lint`

Also run `make test-assertions` — your new test must not trip the assertion scanner.

## Test Verification (NON-NEGOTIABLE)

Run only your own new/affected tests — NOT the full suite:
```bash
uv run pytest tests/unit/.../test_i_00105_context_pct... -v
```
Do not report `tests_passed: true` unless they pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "I-00105",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/.../test_i_00105_context_pct... — <RED failure line captured>",
  "blockers": [],
  "notes": "New function name + signature; safety_buffer default chosen; NULL max_output fallback behaviour."
}
```

## Lifecycle Commands

Start: `uv run iw step-start I-00105 --step S03`
On success: write the report, then
`uv run iw step-done I-00105 --step S03 --report ai-dev/work/I-00105/reports/I-00105_S03_Backend_report.md`
On failure: `uv run iw step-fail I-00105 --step S03 --reason "<brief reason>"`
You MUST call `step-done` (with `--report`) or `step-fail` before exiting.
