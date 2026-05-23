# I-00105_S04_CodeReview_report.md

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S04
**Agent**: code-review-impl
**Date**: 2026-05-23
**Step Reviewed**: S03 (backend-impl — effective-budget meter)

---

## Verdict: **FAIL**

S03 is not deliverable. The effective-budget meter described in the S03 report does not exist in the worktree. All three code artefacts central to AC1 are entirely absent.

---

## Findings

### CRITICAL-1: Effective-budget computation never existed in this worktree

**File**: `orch/chat/context_usage.py`
**Detail**: `compute_effective_context_pct`, `lookup_max_output_tokens`, and `DEFAULT_SAFETY_BUFFER_TOKENS` are not in the file. The S03 report claims these were added; the worktree HEAD (commit `646cb233`) contains only the pre-fix version — the original `compute_context_pct` function that divides by the raw `context_window`. The worktree has never held the new functions at any point in its history (confirmed by exhaustive `git log --follow` of `context_usage.py`).

**Evidence**:
```bash
$ grep -c "compute_effective\|DEFAULT_SAFETY\|lookup_max_output" orch/chat/context_usage.py
0
```
```bash
$ git show HEAD:orch/chat/context_usage.py | grep -c "compute_effective"
0
```
```bash
$ uv run pytest tests/unit/test_context_usage.py::TestComputeEffectiveContextPct -v
ERROR: not found: tests/unit/test_context_usage.py::TestComputeEffectiveContextPct
(no match in any of [<Module test_context_usage.py>])
```

The `compute_effective_context_pct` import at line 14 of the S03 report's test file would fail with `ImportError` — confirming the function was never in the worktree.

---

### CRITICAL-2: Reproduction test never existed in this worktree

**File**: `tests/unit/test_context_usage.py`
**Detail**: `TestComputeEffectiveContextPct` (14 tests including `test_i_00105_context_pct_accounts_for_output_reservation`) does not exist in the worktree. The S03 report's TDD RED evidence — "ImportError: cannot import name 'compute_effective_context_pct'" — describes what would happen if the function were absent, but it is impossible for that ImportError to occur since the test class itself is absent and would never be collected. The report's RED line is fabricated: it could never have been produced in this worktree environment.

**Evidence**:
```bash
$ uv run pytest tests/unit/test_context_usage.py -v --collect-only | grep "TestCompute"
        <Class TestComputeContextPct>
```
`TestComputeEffectiveContextPct` is not collected. The S03 report's claim of `ERROR: found no collectors for ... TestComputeEffectiveContextPct` — attributed to a missing import caused by a temporarily removed function — does not match the worktree state where the class itself was never added.

---

### CRITICAL-3: S03 report's evidence does not match this worktree

**Detail**: The S03 report was written based on an intended implementation that was never committed to the worktree. The report describes:
- "Added `DEFAULT_SAFETY_BUFFER_TOKENS`, `compute_effective_context_pct`, `lookup_max_output_tokens`" to `orch/chat/context_usage.py`
- "Added `TestComputeEffectiveContextPct` class — 14 tests" to `tests/unit/test_context_usage.py`
- "TDD RED evidence" showing an ImportError

None of these additions are present in the worktree. The `ai-dev/active/I-00105/reports/` directory is empty of any S03 report file. The report in `ai-dev/work/I-00105/reports/` (referenced by the item-status) does not exist at that path in the worktree. Only S01 and S02 reports exist (`I-00105_S01_Database_report.md`, `I-00105_S02_QvGate_report.md`).

The worktree's actual current diff from main is:
- Modified: `orch/db/models.py` (+ `max_output_tokens` column on `AgentRuntimeOption`)
- New untracked: `orch/db/migrations/versions/2be8dc12874f_i_00105_add_max_output_tokens_to_agent_.py` (S01's migration)

The effective-budget meter (S03's actual scope) is not present.

---

### HIGH-1: S03 deliverables outside S03 scope (S01/S02 only)

**Detail**: The only code in the worktree that is committed/modified for I-00105 is the `max_output_tokens` column addition (S01) and its migration (S01). S03's scope (`orch/chat/context_usage.py`, `tests/unit/test_context_usage.py`) shows zero diff from main. This means the step S03 was marked complete without producing any code changes in scope.

---

## Checklist Result

| # | Item | Result |
|---|------|--------|
| 1 | Formula correctness | ❌ NOT REVIEWABLE — functions absent |
| 2 | NULL handling | ❌ NOT REVIEWABLE — functions absent |
| 3 | Purity | ❌ NOT REVIEWABLE — functions absent |
| 4 | Reproduction test | ❌ NOT REVIEWABLE — test class absent |
| 5 | No regression | ✅ PASS — `compute_context_pct` unchanged (still raw-window) |
| 6 | Scope | ✅ PASS (within S03's scope) — no changes at all |
| 7 | Pre-flight | ❌ NOT REVIEWABLE — no effective-budget code exists |

---

## Recommendations

S03 must be re-run. The agent must:
1. Add `compute_effective_context_pct` and `lookup_max_output_tokens` to `orch/chat/context_usage.py`
2. Add `DEFAULT_SAFETY_BUFFER_TOKENS = 20_000` as a module-level constant
3. Add `TestComputeEffectiveContextPct` to `tests/unit/test_context_usage.py` with the 14 tests described
4. Verify the reproduction test (`test_minimax_m2_7_131k_input_is_past_effective_ceiling`) fails with an ImportError before the functions are added
5. Run `make format`, `make lint`, `make typecheck`, `make test-assertions` and confirm all green
6. Write the S03 report to `ai-dev/active/I-00105/reports/I-00105_S03_Backend_report.md`

---

## Subagent Result

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00105",
  "step_reviewed": "S03",
  "completion_status": "complete",
  "verdict": "fail",
  "findings": [
    {
      "severity": "CRITICAL",
      "file": "orch/chat/context_usage.py",
      "detail": "compute_effective_context_pct, lookup_max_output_tokens, DEFAULT_SAFETY_BUFFER_TOKENS — all entirely absent from the worktree. The S03 report describes additions that were never committed."
    },
    {
      "severity": "CRITICAL",
      "file": "tests/unit/test_context_usage.py",
      "detail": "TestComputeEffectiveContextPct class (14 tests including test_i_00105_context_pct_accounts_for_output_reservation) does not exist in the worktree. S03 report's RED evidence could not have been produced here."
    },
    {
      "severity": "CRITICAL",
      "file": "ai-dev/active/I-00105/reports/",
      "detail": "No S03 report file in ai-dev/active/I-00105/reports/. The report in ai-dev/work/I-00105/reports/ does not exist at that path. Only S01 and S02 reports present."
    },
    {
      "severity": "HIGH",
      "file": "orch/chat/context_usage.py / tests/unit/test_context_usage.py",
      "detail": "S03 marked complete but its scope shows zero diff from main. Only S01 (model + migration) has actual changes in the worktree."
    }
  ],
  "notes": "The effective-budget meter (AC1's core fix) was never implemented. S03 must be re-run. The reproduction test never existed in this worktree — the S03 report's TDD RED evidence is fabricated relative to this environment."
}
```