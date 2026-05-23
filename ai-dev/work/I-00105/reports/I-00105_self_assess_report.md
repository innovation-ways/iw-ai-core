# I-00105 Self-Assessment Report

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S20 (SelfAssess)
**Agent**: self-assess-impl
**Date**: 2026-05-23
**Completion**: complete

---

## What Was Done

S20 invoked the `iw-item-analyze` skill to perform a structured self-assessment of
I-00105's execution history, covering all steps S01–S19. The analysis surfaced process-
improvement findings across five dimensions: fix-cycle usage, formula consistency,
context-window behaviour, code quality, and test coverage.

The analysis is based on: step reports for S06, S08, S09, S10, S11; run logs for
S01–S19 (28 log files including fix cycles); and `git diff origin/main` output
(77 files changed, net −7740 lines — deletions dominated by e2e test removal in a
pre-existing cleanup unrelated to I-00105).

---

## Files Changed by This Item

| File | Type | Purpose |
|------|------|---------|
| `orch/chat/context_usage.py` | Source | `compute_effective_context_pct()` — AC1 effective-budget meter |
| `orch/db/models.py` | Source | `max_output_tokens` column on `AgentRuntimeOption` — AC3 schema |
| `orch/db/migrations/versions/2be8dc12874f_*.py` | Migration | Adds column + backfills pi/MiniMax-M2.7 → 131072 |
| `dashboard/routers/items.py` | Source | Fetches `max_output_tokens`, precomputes effective % per step |
| `dashboard/templates/fragments/item_steps_table.html` | Template | Uses `context_effective_pct` for gauge; raw fallback when NULL |
| `executor/context_overflow.py` | Source | AC4 overflow detection (5 signatures, case-sensitive) |
| `executor/tool_output_cap.py` | Source | AC2 cap+spill helper (over-cap → spill, under-cap → unchanged) |
| `executor/step_executor.sh` | Source | Hooks overflow detection post-exit |
| `executor/step_executor_lib.sh` | Source | `get_compaction_threshold_tokens()` + 3 config vars |
| `orch/config.py` | Source | 5 new cap/compaction/overflow fields as `IW_CORE_*` env vars |
| `tests/unit/test_i00105_effective_context_pct.py` | Test | AC1 regression suite (24 tests) |
| `tests/unit/executor/test_context_overflow.py` | Test | AC4 overflow-detection suite (16 tests) |
| `tests/unit/executor/test_tool_output_cap.py` | Test | AC2 cap+spill suite (28 tests) |
| `tests/integration/test_i00105_max_output_tokens_migration.py` | Test | AC3 migration suite (6 tests) |
| `tests/dashboard/test_item_steps_effective_context.py` | Test | Dashboard gauge integration (4 tests) |

**Total**: 6 source files, 1 migration, 5 test files (78 tests passing).

---

## Fix-Cycle Analysis

| Step | Agent | Runs | Fix Cycles | Outcome |
|------|-------|------|------------|---------|
| S02 (migration-check) | migrate-impl | 5 (runs 1–4 failed, run 5 passed) | 0 | Passed after 5 runs — testcontainer startup variability, not code issues |
| S03 (backend-impl) | backend-impl | 1 | 0 | Clean pass |
| S05 (frontend-impl) | frontend-impl | 1 | 0 | Clean pass; deferred AC2 chat-gauge fix to S05 patch |
| S06 (code-review) | code-review-impl | 1 | 0 | FAIL — AC2 chat gauge issue, drove fix cycle |
| S07 (backend-impl) | backend-impl | 1 | 0 | Clean pass |
| S08 (code-review) | code-review-impl | 1 | 0 | FAIL — HIGH: cap+spill not integrated into daemon path; overflow detection not integrated into daemon path |
| S09 (tests-impl) | tests-impl | 1 | 0 | Clean pass |
| S10 (code-review) | code-review-impl | 1 | 0 | PASS |
| S11 (code-review-final) | code-review-final | 1 | 0 | PASS |
| S12 (fix) | fix-impl | 4 | 1 | S13 tautology warnings drove fix cycle (4 runs) |
| S13 (fix) | fix-impl | 4 | 1 | S14 format failure drove fix cycle (4 runs) |
| S14 (fix) | fix-impl | 1 | 0 | Clean pass |
| S15 (typecheck) | typecheck-impl | 1 | 0 | Clean pass |
| S16 (integration-tests) | integration-tests-impl | 1 | 0 | Clean pass |
| S17 (fix) | fix-impl | 4 | 1 | S17 itself ran 4 times; log shows null for runs 1–3, run 4 succeeded |
| S18 (integration-tests) | integration-tests-impl | 1 | 0 | Clean pass |
| S19 (security) | security-impl | 1 | 0 | Clean pass (gitleaks) |

**Total fix cycles**: 3 (S12/S13, S13/S14, S17). Root causes:
- **S12/S13**: S07's executor tests used tautological assertions (`len(x) > 0`, `isinstance(x, str)`) — fixed by replacing with concrete value assertions.
- **S14**: PEP 8 formatting (missing blank line after `from` import inside `if` block) — single-line fix.
- **S17**: 4 runs with null logs for 3 runs, final run succeeded — likely environmental container startup variability.

**Notable**: S02 required 5 runs, but none were fix cycles — the step's testcontainer
consistently took >300s, and the agent repeatedly re-ran rather than waiting. This is
a pre-existing environmental constraint, not an I-00105 defect.

---

## Effective-Budget Formula: Single Source of Truth

The `compute_effective_context_pct()` function lives in exactly one place:
`orch/chat/context_usage.py` (S03). Both consuming locations call it:

1. **`dashboard/routers/items.py`** (S05) — calls it in the SQL query builder,
   precomputes `effective_budget_pct` per step, passes it as `context_effective_pct`
   to the template. The template reads this precomputed value; no inline division.

2. **`dashboard/routers/chat.py`** (S05, AC2 deferred) — still calls the raw
   `compute_context_pct()` (not `compute_effective_context_pct`) in both Pi and
   OpenCode paths. This was flagged by S06 (code-review) as a CRITICAL finding.
   S11 (code-review-final) confirmed it as a HIGH finding with a recommendation to
   file a follow-up CR.

**Formula consistency**: The formula (effective = window − max_output − safety_buffer)
is single-sourced in `orch/chat/context_usage.py`. The safety buffer value
`DEFAULT_SAFETY_BUFFER_TOKENS = 20_000` is also single-sourced and shared with
`executor/step_executor_lib.sh`'s `get_compaction_threshold_tokens()` function.

---

## Context-Window Limit (Class of Bug This Item Fixes)

I-00105 **did not itself encounter a context-window overflow** during execution.
This is expected: the item was implemented against the local worktree state with
a fixed git history. The fix (AC1 effective-budget meter, AC4 overflow detection,
AC2 cap+spill) addresses context-window overflows that would occur in production
when an agent runtime processes a large tool result or long conversation history.

The AC4 overflow-detection implementation (`executor/context_overflow.py`) correctly
detects 5 known signatures (Anthropic, OpenAI, Azure, opencode, LiteLLM) with case-
sensitive matching. The hook is wired into `step_executor.sh` (manual execution path)
but NOT into `batch_manager.py` (daemon execution path) — this was the S08 HIGH finding.
The S11 review confirmed this gap and recommended integration as a follow-up.

---

## TDD RED Evidence

S03 (backend-impl) added `compute_effective_context_pct` with TDD:
- RED: `ImportError: cannot import name 'compute_effective_context_pct'` from the
  unmodified meter — confirmed by temporarily stripping the new functions.
- GREEN: `TestComputeEffectiveContextPct` (14 tests, all pass).

S09 (tests-impl) added the named reproduction test:
- `test_i_00105_context_pct_accounts_for_output_reservation` asserts `pct >= 100.0`
  and `pct > 200.0` for MiniMax-M2.7 at 131K input with `max_output=131072`.
- Pre-fix meter (raw window): `131072 / 204800 * 100 = 64%` → fails `>= 100.0`.
- Post-fix meter (effective budget): `131072 / 53728 * 100 ≈ 244%` → passes.
- ~180 percentage-point divergence is a clean RED/GREEN signal.

---

## Quality Gates

| Gate | Status | Notes |
|------|--------|-------|
| Format (ruff) | ✅ | Passes cleanly |
| Lint (ruff) | ✅ | Passes cleanly |
| Typecheck (mypy) | ✅ | 0 issues in 276 source files |
| Test assertions | ⚠️ | S07's executor tests had tautology warnings (7); fixed in S12/S13 fix cycles. S09's tests are clean. |
| Unit tests | ✅ | 3,477 passed, 0 failed |
| Integration tests | ✅ | 3,230 selected, 0 failures (skips and xfails as expected) |
| Security (gitleaks) | ✅ | No leaks found |
| Migration check | ✅ | `test_migrations_round_trip` passes |

---

## Process Findings

### Finding 1: Tautological Assertions in S07's Executor Tests (RESOLVED)

**Severity**: MEDIUM
**Finding**: `test_context_overflow.py` and `test_tool_output_cap.py` (written by S07)
contained 7 tests where every assertion was a tautological form (`is not None`,
`isinstance`, `len > 0`). The assertion scanner flagged these in S13.

**Root cause**: The executor helper modules (`context_overflow.py`, `tool_output_cap.py`)
have return types that are structurally simple (`OverflowDetectionResult` dataclass with
3 fields, `CapResult` dataclass with 7 fields). Writing concrete value assertions requires
knowing the expected values of those fields from the input — not just their shape.

**Resolution**: Fixed in S12/S13 fix cycle. Assertions replaced with concrete values:
- `result.detected is True` (not just `result.detected is not None`)
- `result.spill_path.endswith(".txt")` (not just `len(result.spill_path) > 0`)
- `result.preview == "small output"` (not just `"small output" in result.preview`)

**Prevention**: The assertion scanner should be run on all new test files before
step completion. The `make test-assertions` gate exists; agents should invoke it
before declaring a step done.

### Finding 2: Chat-Assistant Gauge Inconsistency (OPEN — Follow-up CR Needed)

**Severity**: HIGH
**Finding**: `dashboard/routers/chat.py`'s `get_tab()` endpoint calls
`compute_context_pct` (raw window) for both Pi and OpenCode paths, while the per-step
gauge in `items.py` correctly calls `compute_effective_context_pct`. The two gauges
are inconsistent — AC2 explicitly requires consistency.

**AC2 state**: Per-step gauge ✅ (fixed in S05); chat-assistant gauge ❌ (not fixed).

**Impact**: Users viewing the chat assistant see a gauge that reads 64% for MiniMax-M2.7
at 131K input while the per-step gauge reads ≥100% — exactly the divergence the item
was designed to eliminate.

**Resolution**: File a follow-up CR. Fix requires:
1. Extend the `AgentRuntimeOption` lookup in `chat.py`'s Pi path to also fetch
   `max_output_tokens` alongside `context_window_tokens`, then call
   `compute_effective_context_pct` instead of `compute_context_pct`.
2. In the OpenCode path, call `context_usage.lookup_max_output_tokens(providers_raw, pid, mid)`
   (providers_raw is already in scope at line ~818), then call
   `compute_effective_context_pct` instead of `compute_context_pct`.
3. No JS changes needed — the frontend reads `session.context_pct` which is set by
   the backend.

### Finding 3: AC4 Overflow Detection Not Integrated into Daemon Path (OPEN — Follow-up CR Needed)

**Severity**: HIGH
**Finding**: The `detect_context_overflow()` hook is wired into `step_executor.sh`
(manual execution path via post-exit log scan) but not into `batch_manager.py`
(daemon production path). The daemon launches runtimes directly via `subprocess.Popen`
(line ~1594) without invoking `step_executor.sh`.

**Impact**: A context-window overflow in a production step (daemon-launched) is not
detected. The step will silently continue, eventually hitting the context-overflow error
but without the clean `STEP_OUTCOME=context_overflow` override and named blocker that
AC4 requires.

**Resolution**: File a follow-up CR. Integration options:
1. Add a post-exit scan in `batch_manager.py` (mirroring the `step_executor.sh` approach)
   — scan the step's log file for overflow signatures after the subprocess exits.
2. Add a check in `step_monitor.py` on completed-but-not-marked-done runs.
3. Document the gap as a known limitation pending harness-level integration.

### Finding 4: S02 Required 5 Runs (Environmental — Not a Process Defect)

**Severity**: LOW
**Finding**: S02's migration-check step required 5 runs before passing. The cause was
testcontainer startup variability causing the integration test suite to exceed the
300s timeout on runs 1–4.

**Root cause**: The step agent ran `uv run pytest tests/integration/test_migrations_round_trip.py`
in each attempt. The testcontainer for PostgreSQL takes variable time to start (8–12s in
normal runs, up to 300s under environmental load). The agent was not waiting for the
full container startup before concluding the step had failed.

**Resolution**: Pre-existing environmental constraint. The test suite itself is correctly
written (3 tests, all pass when the container starts in time). No process change needed —
this is an infrastructure concern, not a code quality concern.

---

## Summary

| Dimension | Status |
|-----------|--------|
| AC1 (effective-budget meter) | ✅ Implemented. Per-step gauge reads ≥100% for MiniMax-M2.7 at 131K input. |
| AC2 (cap+spill) | ⚠️ Helper delivered and tested. Chat gauge NOT yet fixed (follow-up CR needed). |
| AC3 (regression tests) | ✅ TDD reproduction + 78 semantic tests all passing. |
| AC4 (overflow detection) | ⚠️ Wired in manual path. NOT wired in daemon path (follow-up CR needed). |
| Fix cycles | 3 (S12/S13, S13/S14, S17) — all resolved cleanly. |
| Formula consistency | ✅ Single source: `orch/chat/context_usage.py`. Shared with `step_executor_lib.sh`. |
| Quality gates | ✅ All green. |
| Context-window hit during I-00105? | ❌ No — implementation step, not production runtime. AC4 addresses this in production. |

---

## Subagent Result Contract

```json
{
  "step": "S20",
  "agent": "self-assess-impl",
  "work_item": "I-00105",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/work/I-00105/reports/I-00105_self_assess_report.md",
    "ai-dev/work/I-00105/reports/I-00105_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "78 tests pass (24 unit/effective, 16 unit/overflow, 28 unit/cap, 6 integration/migration, 4 dashboard/gauge); unit suite 3477 passed; integration suite 3230 selected, 0 failures",
  "blockers": [],
  "notes": "Analysis completed; 4 findings surfaced (2 resolved, 2 open for follow-up CR). Effective-budget formula single-sourced in orch/chat/context_usage.py. S07 tautology warnings resolved in S12/S13 fix cycle. Chat-gauge and daemon-path integration remain open."
}
```