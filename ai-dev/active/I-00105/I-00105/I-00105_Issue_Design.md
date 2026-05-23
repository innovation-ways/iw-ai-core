# I-00105: Workflow step fails when its agent runtime overflows the model context window

**Type**: Issue
**Severity**: High
**Created**: 2026-05-22
**Reported By**: Operator (dashboard review of CR-00076)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This incident **adds one Alembic migration** (a new nullable column on `agent_runtime_options`). The Database step writes the migration file only; the daemon applies it. No other schema change.

## Description

A workflow step dies when its agent runtime overflows the model's context window. The runtime auto-compacts and limps on, but the step never completes cleanly: no `step-done`, no report, junk artifacts left behind, and in the triggering case the agent even whitelisted its own tests in the assertion baseline. The step half-finishes and silently corrupts its own output instead of completing within budget or failing cleanly.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant: the executor (`executor/`) launches agent runtimes (`opencode`, `claude`, `pi`); the dashboard surfaces a per-step context gauge; `orch/chat/context_usage.py` computes context-window usage; `agent_runtime_options` (CR-00066) stores `context_window_tokens` per runtime. The implementation approach is backed by research **R-00078** (`docs/research/R-00078-agent-tool-output-context-capping.md`) — read it before implementing.

## Steps to Reproduce

1. Run a large implementation step on a small-context runtime — CR-00076 step S01 (`backend-impl`) on the `pi` runtime with `minimax/MiniMax-M2.7` (204,800-token window, 131,072-token max output).
2. The agent accumulates tool output across the step (many file reads, edits, `pytest` runs — one run was the full integration suite).
3. Accumulated input passes the model's effective input budget.

**Expected**: The step completes within budget, or — if it genuinely cannot — fails cleanly with a clear blocker and no half-written artifacts.

**Actual**: The runtime returns `400 invalid_request_error: invalid params, context window exceeds limit`, auto-compacts, and continues in a degraded state. The step never calls `step-done`, leaves junk artifacts (a duplicated nested directory, self-whitelisted tests), and runs commands it was told not to. The dashboard context gauge read **64%** at the time — it did not warn.

## Root Cause Analysis

Four compounding causes, all confirmed against the code and research R-00078:

1. **The context gauge measures against the wrong denominator — in two separate places.** Two independent code paths divide used tokens by the *full* context window. (a) The chat-assistant gauge goes through `orch/chat/context_usage.py:149`, which computes `pct = (used_tokens / context_window) * 100.0`. (b) The **per-step workflow gauge — the one that read 64% in the triggering incident** — does **not** call `context_usage.py` at all: it computes its own raw-window percentage directly in the template `dashboard/templates/fragments/item_steps_table.html` (`ctx_pct = ctx_peak / ctx_window * 100`, then clamps to 100); `dashboard/routers/items.py` only resolves `context_window_tokens` per step and passes the token counts down. A model's **effective input budget is `window − max_output_tokens − safety_buffer`**, not the full window. For MiniMax-M2.7 that is `204,800 − 131,072 − buffer ≈ 65–74K`, roughly a third of the nominal 204,800. So the gauge reports ~64% when input is ~131K — at or past the real ceiling. **The fix must correct both division sites** (the meter for the chat gauge, and the template/router path for the per-step gauge). There is no `max_output_tokens` stored anywhere: `agent_runtime_options` (`orch/db/models.py:56`, CR-00066) has `context_window_tokens` (`orch/db/models.py:74`) but no output reservation.

2. **No executor-side cumulative tool-output cap.** `executor/step_executor.sh` launches the runtime with no bound on how much tool output accumulates over the step. The `pi` runtime caps a *single* result (~50 KB) but nothing bounds the *cumulative* total across dozens of reads/edits/test runs — R-00078 finding "pi's per-call cap does not bound accumulated context".

3. **Compaction triggers too late.** The runtime compacts only near the hard limit; calibrated to the nominal window it fires far past the effective ceiling, so a request overflows before compaction can help.

4. **No executor-side overflow detection — the runtime self-recovers silently.** When the runtime hits the limit it returns `400 invalid_request_error: context window exceeds limit`, then auto-compacts and *continues* in a degraded state. `executor/step_executor.sh` has no hook that observes this error, so the step is never failed cleanly: it limps on, never calls `step-done`, and leaves the junk artifacts described above. Causes 1–3 reduce the *likelihood* of overflow; nothing converts an overflow that still happens into a clean, clearly-attributed failure.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/chat/context_usage.py` | Chat-assistant meter; computes usage against the full window; no effective-budget calculation → misleading gauge |
| `orch/db/models.py` (`agent_runtime_options`) | No `max_output_tokens` column → effective budget cannot be computed |
| `dashboard/routers/items.py` · `dashboard/templates/fragments/item_steps_table.html` | Per-step gauge **computes its own** raw-window `ctx_peak / ctx_window` percentage in the template (does not use `context_usage.py`) — this is the gauge that read 64% in the incident |
| `dashboard/routers/chat.py` · `dashboard/static/chat_assistant/chat.js` | Chat-assistant gauge shares the same meter |
| `executor/step_executor.sh` | No cumulative tool-output cap; no proactive-compaction calibration; no detection of a context-overflow error → the step limps on in a degraded state instead of failing cleanly |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `max_output_tokens` column to `agent_runtime_options` + Alembic migration + backfill known runtimes | — |
| S02 | qv-gate | `migration-check` — Alembic round-trip + drift | — |
| S03 | backend-impl | Effective-budget meter in `orch/chat/context_usage.py` | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | frontend-impl | Dashboard context gauge displays effective-budget % | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | backend-impl | Executor per-tool-output cap + disk spill + compaction calibration + context-overflow detection → clean `step-fail` | — |
| S08 | code-review-impl | Review S07 | — |
| S09 | tests-impl | Reproduction test + regression tests | — |
| S10 | code-review-impl | Review S09 | — |
| S11 | code-review-final-impl | Global cross-step review | — |
| S12..S19 | qv-gate | lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S20 | self-assess-impl | Item self-assessment | — |

Agent slugs: `database-impl`, `backend-impl`, `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: `agent_runtime_options` — add `max_output_tokens INTEGER NULL`
- **Migration notes**: One new Alembic revision. Column is nullable; backfill known runtimes in the migration (`pi`/MiniMax-M2.7 → `131072`; claude/opencode rows → their model's documented max output, or leave NULL where unknown). `migration-check` (S02) must pass.

### Code Changes

- **Files to modify**: `orch/db/models.py`, `orch/db/migrations/versions/<new>.py`, `orch/chat/context_usage.py`, `dashboard/routers/items.py`, `dashboard/routers/chat.py`, `dashboard/templates/fragments/item_steps_table.html`, `dashboard/static/chat_assistant/chat.js`, `executor/step_executor.sh` (+ a helper script if needed), `orch/config.py` (cap / threshold config), `docs/IW_AI_Core_Daemon_Design.md` (document the executor cap, if appropriate).
- **Nature of change**: add a stored output reservation; compute and display an *effective* budget; cap and spill tool output at the executor; calibrate the compaction trigger; detect a context-overflow error and finalize the step as a clean failure.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00105_Issue_Design.md` | Design | This document |
| `I-00105_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/I-00105_S01_Database_prompt.md` | Prompt | S01 — schema + migration |
| `prompts/I-00105_S03_Backend_prompt.md` | Prompt | S03 — effective-budget meter |
| `prompts/I-00105_S04_CodeReview_prompt.md` | Prompt | S04 — review S03 |
| `prompts/I-00105_S05_Frontend_prompt.md` | Prompt | S05 — dashboard gauge |
| `prompts/I-00105_S06_CodeReview_prompt.md` | Prompt | S06 — review S05 |
| `prompts/I-00105_S07_Backend_prompt.md` | Prompt | S07 — executor capping + compaction |
| `prompts/I-00105_S08_CodeReview_prompt.md` | Prompt | S08 — review S07 |
| `prompts/I-00105_S09_Tests_prompt.md` | Prompt | S09 — reproduction + regression tests |
| `prompts/I-00105_S10_CodeReview_prompt.md` | Prompt | S10 — review S09 |
| `prompts/I-00105_S11_CodeReview_Final_prompt.md` | Prompt | S11 — global review |
| `prompts/I-00105_S20_SelfAssess_prompt.md` | Prompt | S20 — self-assessment |

Reports are created during execution in `ai-dev/work/I-00105/reports/`.

## Test to Reproduce

The bug is a calibration error in the meter, so the reproduction test targets the **effective-budget computation** — the deterministic, unit-testable core. It fails before the fix (the meter has no notion of `max_output`) and passes after.

```python
def test_i_00105_context_pct_accounts_for_output_reservation():
    """A model whose max_output is a large fraction of its window must report
    usage against the EFFECTIVE budget (window - max_output - buffer), not the
    raw window. FAILS pre-fix (meter divides by the full window)."""
    # MiniMax-M2.7: window 204,800, max_output 131,072.
    # used 131,072 input tokens => against the raw window that is 64%,
    # but against the effective budget it is already at/over 100%.
    pct = compute_effective_context_pct(
        used_tokens=131_072,
        context_window=204_800,
        max_output_tokens=131_072,
    )
    assert pct >= 100.0, (
        f"131K input on a 205K/131K-output model is past the effective "
        f"ceiling; meter must report >=100%, got {pct}"
    )
```

(The exact function name / signature is the implementer's choice — the test pins the *behaviour*: output reservation is subtracted before the percentage is computed.)

## Acceptance Criteria

### AC1: Bug is fixed — context usage is measured against the effective budget

```
Given a model whose max_output_tokens is a large fraction of its context window
     (e.g. MiniMax-M2.7: 204,800 window / 131,072 max output)
When the context gauge computes usage for a step whose input is ~131K tokens
Then it reports usage against the effective budget (window - max_output - buffer)
And the reported percentage is at or above 100%, not ~64%
```

### AC2: Executor caps and spills oversized tool output

```
Given a step whose tool produces an output larger than the configured per-output cap
When the executor processes that tool result
Then the full result is written to a file under the step work directory
And the agent receives a head+tail preview plus the file path (recoverable),
     never an in-place head/tail snippet with no spill file
```

### AC3: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproducing test (effective-budget computation) passes
And regression tests cover the meter, the migration, the executor cap, and the
     context-overflow-detection helper
```

### AC4: A genuine context overflow fails the step cleanly

```
Given a workflow step whose agent runtime emits a context-window-overflow error
     (e.g. 400 invalid_request_error: context window exceeds limit)
When the executor observes that error and the step has not completed cleanly
Then the executor finalizes the step as failed with a clear blocker that names
     the context overflow as the cause
And the step does not silently limp on in a degraded state past the overflow
```

## Regression Prevention

- A unit test pins the effective-budget formula so the meter can never silently revert to dividing by the raw window.
- `max_output_tokens` becomes a first-class stored field, so adding a new runtime forces the operator to record its output reservation.
- The executor cap is config-driven (`orch/config.py`) with a documented default, and a test asserts oversized output is spilled, not inlined.
- The executor's context-overflow-detection signature set is pinned by a unit test, so an overflow that still happens can never again silently limp on instead of failing with a clear blocker.
- `migration-check` (S02) guards the schema change against model↔migration drift.

## Dependencies

- **Depends on**: R-00078 (research — informs S03/S05/S07 implementation). Not a blocking work-item dependency.
- **Blocks**: None.
- **Related**: a separate CR will cover "make workflow steps smaller" (a design-template change), the other half of the context-overflow mitigation. I-00105 is the runtime/executor fix only.

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/chat/**`
- `orch/config.py`
- `dashboard/routers/items.py`
- `dashboard/routers/chat.py`
- `dashboard/templates/**`
- `dashboard/static/chat_assistant/**`
- `executor/**`
- `tests/**`
- `docs/IW_AI_Core_Daemon_Design.md`

## TDD Approach

- Reproducing test: `test_i_00105_context_pct_accounts_for_output_reservation` — fails pre-fix (meter has no output reservation), passes after S03.
- Unit tests: effective-budget computation across runtimes (large vs small `max_output`, NULL `max_output` falls back gracefully); the executor cap helper (oversized → spill file + preview; under-cap → passthrough unchanged); the context-overflow-detection helper (runtime output carrying a `context window exceeds limit` signature → detected with a clear blocker message; clean output → not detected).
- Integration tests: the migration applies and backfills; `compute_effective_context_pct` reads `max_output_tokens` from `agent_runtime_options` end-to-end.

**Assertion scoping** — Tests must assert specific values (e.g. `pct >= 100.0`, the spill file exists and contains the full output), not just shape. A test that only checks "a percentage was returned" or "some string came back" does not prove the fix.

## Notes

- Out of scope (operator decision): routing steps to a larger/different model; and "make workflow steps smaller" (separate CR).
- The dashboard gauge bug is backend-rooted (the meter); it is verified with `tests/dashboard/` TestClient tests, not browser verification — reproducing a real context overflow in a browser is impractical.
- `max_output_tokens` backfill: use documented values where known; leave NULL where unknown — the meter must treat NULL as "no reservation" and fall back to the raw window (degrading to today's behaviour rather than crashing).
- Research R-00078 contains the cross-harness survey (Claude Code 30 KB Bash cap + disk spill; opencode 40K/20K prune thresholds; effective-budget formula) behind S05/S07 — implementers should follow its recommendations.
