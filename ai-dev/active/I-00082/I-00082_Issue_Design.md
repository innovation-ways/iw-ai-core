# I-00082: Fix-cycle agent has no allowed_paths enforcement — drifts or reverts

**Type**: Issue
**Severity**: High
**Created**: 2026-05-15
**Reported By**: sergio (operator); diagnosed during CR-00053 manual rescue
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This incident
adds no Docker usage.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This incident leaves migrations unchanged.

## Description

When a quality-validation gate fails, the daemon spawns a fix-cycle LLM agent
with the failing gate's diagnostic output. The agent is free to edit any file
in the worktree — there is no enforcement of `workflow-manifest.json:scope.allowed_paths`
during fix cycles. This produces two distinct deadlock modes that have already
cost ~14 wasted fix cycles on a single CR (see CR-00053 below).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.
Most relevant: `orch/daemon/fix_cycle.py` is the spawn site;
`executor/scope_gate.py` already exists as a merge-time gate (opt-in via
`.iw-orch.json:scope_gate_enabled`); `orch/daemon/CLAUDE.md` describes the
fix-cycle lifecycle.

## Steps to Reproduce

### Drift mode (CR-00053 / S09, fix cycle 3)

1. Approve a CR with a tightly-scoped `allowed_paths` (e.g., 5 files).
2. Let the daemon execute through QV gates until one fails for any reason
   (e.g., a transient lint error in an unrelated file pulled in by a sibling
   item's chore commit).
3. Observe: the fix-cycle agent edits files outside `allowed_paths` —
   confirmed concretely on CR-00053 where the agent added new RAG
   token-counting tests in `tests/integration/rag/test_chat_repo.py` to
   "fix" a lint error reported in a different test file. Those new tests
   themselves had 5 lint errors (`F401`, `F821`×2, `E501`, `ARG005`),
   reigniting the lint failure.

**Expected**: agent refuses to edit any path not in `allowed_paths` and
escalates to operator.

**Actual**: agent edits anywhere; new errors compound; cycle 3 exhausts and
the step is marked `failed needs human review`.

### Revert mode (CR-00053 / S15, fix cycle 2)

1. Same CR as above. Operator manually applies a legitimate carry-over fix
   to a file outside `allowed_paths` (concrete example: changed
   `BatchStatus.executing` → `BatchStatus.completed` in
   `tests/integration/test_dashboard_actions.py:540` because F-00082 made
   `executing` a valid cancel state, and the matching test fix from
   CR-00052's merge was not yet in the worktree's branch base).
2. Operator runs `iw step-restart S15`; daemon picks up and runs the qv-gate.
3. The gate still fails for an unrelated reason (here, a transient
   diff-coverage miscount caused by stale `origin/main` ref — see I-00084).
4. Daemon spawns the fix-cycle agent.
5. Observe: the agent reverts the operator's edit on the out-of-scope file
   because the agent's heuristic interprets out-of-scope edits as scope
   creep to be undone.

**Expected**: agent leaves out-of-scope operator edits intact, OR explicitly
flags the conflict between "fix is needed" and "fix is out of scope" so the
operator can amend `allowed_paths` for that worktree.

**Actual**: edit is silently reverted. Next gate run fails again on the
same root cause. Operator re-applies the edit. The cycle repeats until the
fix-cycle budget is exhausted (CR-00053/S15 reached cycle 3/5 before
operator paused the batch and drove to merge by hand).

## Root Cause Analysis

`orch/daemon/fix_cycle.py` constructs the fix-cycle prompt from the gate
report and the previous fix-cycle prompts but does **not**:

- Inject `workflow-manifest.json:scope.allowed_paths` into the prompt.
- Run a post-cycle `git diff --name-only` against `allowed_paths` to detect
  out-of-scope edits.
- Distinguish operator-applied uncommitted edits from agent-introduced
  uncommitted edits when the cycle starts.

The merge-time gate (`executor/worktree_commit.sh` Step 2.25 →
`executor/scope_gate.py`) does enforce the same list but only at merge
time — by then the fix-cycle has already been wasted. Additionally,
`scope_gate_enabled` defaults to `false` in `.iw-orch.json` for iw-ai-core,
so this gate is not even active for the project where the symptom was
observed.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/fix_cycle.py` | Spawns LLM agents with no scope context |
| Fix-cycle prompt template (in `orch/daemon/fix_cycle.py` or sibling) | Missing `allowed_paths` block |
| `executor/scope_gate.py` | Reused — provides the matching logic; needs a wrapper invokable from Python |
| `.iw-orch.json` (per project) | New optional flag `fix_cycle_scope_enforcement` (default true) |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Pipeline | Inject `allowed_paths` into the fix-cycle prompt; after each cycle, diff against `allowed_paths`; if any out-of-scope file is touched, mark the cycle `escalate-to-operator` (do not auto-revert; do not auto-commit) | — |
| S02 | CodeReview | Per-agent review of S01 | — |
| S03 | Tests | Reproduction test exercising fix-cycle with a fake LLM agent that edits an out-of-scope file; assert the cycle escalates instead of advancing | — |
| S04 | CodeReview | Per-agent review of S03 | — |
| S05 | CodeReview_Final | Cross-agent global review | — |
| S06..S13 | QV Gates | lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S14 | SelfAssess | Self-assessment via iw-item-analyze skill | — |

### Database Changes

- **New tables**: None.
- **Modified tables**: None.
- **Migration notes**: This incident is pure pipeline logic; no schema impact.

### Code Changes

- **Files to modify**: `orch/daemon/fix_cycle.py` (and any sibling prompt-template module — verify via grep at S01).
- **Nature of change**: Read manifest's `scope.allowed_paths` before each cycle; format into prompt; after the cycle's git activity, run `scope_gate.py` (or its Python equivalent) on the diff and treat violations as escalation triggers.

## File Manifest

All files for this work item live under `ai-dev/active/I-00082/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00082_Issue_Design.md` | Design | This document |
| `I-00082_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00082_S01_Pipeline_prompt.md` | Prompt | S01 fix |
| `prompts/I-00082_S02_CodeReview_Pipeline_prompt.md` | Prompt | S02 review |
| `prompts/I-00082_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00082_S04_CodeReview_Tests_prompt.md` | Prompt | S04 test review |
| `prompts/I-00082_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00082_S14_SelfAssess_prompt.md` | Prompt | S14 self-assess |

Reports are created during execution in `ai-dev/work/I-00082/reports/`.

## Test to Reproduce

Add a test under `tests/integration/test_fix_cycle_scope_enforcement.py`:

```python
def test_i00082_fix_cycle_escalates_on_out_of_scope_edit(tmp_path, monkeypatch):
    """When the fix-cycle agent edits a file outside allowed_paths,
    the cycle is marked escalate-to-operator instead of advancing.

    This test should FAIL before the fix and PASS after.
    """
    # Arrange: a fake worktree with a manifest declaring a tight allowed_paths
    # and a fake LLM agent that will write to a file outside that list.
    manifest_path = tmp_path / "workflow-manifest.json"
    manifest_path.write_text(
        '{"scope": {"allowed_paths": ["allowed.py"]}, "steps": []}'
    )
    (tmp_path / "allowed.py").write_text("# in scope\n")
    (tmp_path / "out_of_scope.py").write_text("# pre-existing\n")

    def fake_agent_run(prompt, cwd):
        # Simulate the agent making an out-of-scope edit
        (cwd / "out_of_scope.py").write_text("# agent-edited\n")
        return {"completion_status": "complete"}

    monkeypatch.setattr(
        "orch.daemon.fix_cycle.run_llm_agent", fake_agent_run
    )

    # Act
    result = run_fix_cycle(
        worktree_path=tmp_path,
        item_id="I-99001",
        step_id="S01",
        cycle_number=1,
        gate_failure="lint failed",
    )

    # Assert
    assert result.outcome == "escalate-to-operator", (
        f"expected escalation but got {result.outcome!r} — fix-cycle let the "
        "agent edit a file outside allowed_paths"
    )
    assert "out_of_scope.py" in result.violation_paths
    assert (tmp_path / "out_of_scope.py").read_text() == "# agent-edited\n", (
        "agent's out-of-scope edit must be preserved verbatim — operator "
        "decides whether to amend allowed_paths or revert"
    )
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given an item with scope.allowed_paths = ["a.py"]
When the fix-cycle agent edits "b.py" (outside allowed_paths)
Then the cycle's outcome is "escalate-to-operator" and the daemon does NOT advance the step
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/integration/test_fix_cycle_scope_enforcement.py passes (the reproduction test)
```

### AC3: Operator carry-over fixes are preserved

```
Given the operator has applied an uncommitted edit to a file outside allowed_paths before the fix-cycle starts
When the fix-cycle agent runs
Then the operator's edit is NOT silently reverted by the agent or the post-cycle reconciliation logic
```

### AC4: In-scope fix cycles still work

```
Given the fix-cycle agent edits only files inside allowed_paths
When the cycle finishes
Then the daemon advances the step normally (no regression in the happy path)
```

## Regression Prevention

- The reproduction test above pins the escalation behavior.
- The fix-cycle prompt now includes the `allowed_paths` list verbatim, making
  drift visible to anyone reviewing prompt history.
- Add a daemon log line on every cycle: `fix_cycle scope: allowed_paths=N
  edits_in_scope=K out_of_scope_violations=M` so operators can see at a
  glance whether a stuck step is in revert-mode or drift-mode.

## Dependencies

- **Depends on**: None (uses existing `executor/scope_gate.py` matching
  logic).
- **Blocks**: None operationally; substantially reduces the cost of every
  future stuck-CR rescue (CR-00053 burned ~14 cycles total).

## Impacted Paths

- `orch/daemon/fix_cycle.py`
- `tests/integration/test_fix_cycle_scope_enforcement.py`

## TDD Approach

- Reproducing test: `tests/integration/test_fix_cycle_scope_enforcement.py::test_i00082_fix_cycle_escalates_on_out_of_scope_edit` (above).
- Unit tests: helpers in `orch/daemon/fix_cycle.py` for `_compute_violations(diff_paths, allowed_globs)` — pure-function level coverage of glob matching, multiple violations, empty-list pass-through.
- Integration tests: end-to-end via `run_fix_cycle()` with monkeypatched LLM run, plus an in-scope happy-path regression.

## Notes

This incident is the single most expensive process tax we currently pay
on stuck CRs. Concrete cost on CR-00053 alone (one item):

- S09 (lint): 3 fix cycles, all failed with new lint errors introduced by the agent
- S10 (assertions): 4 fix cycles, all introduced out-of-scope edits
- S14 (integration): 4 fix cycles, included a legitimate one-line carry-over edit but mixed it with scope creep
- S15 (diff-coverage): 3 fix cycles, the second of which silently reverted the operator's S14 carry-over fix (this is what triggered the operator's full-rescue session)

Sibling incidents filed concurrently:

- I-00083 — branch-base drift across in-flight items (the underlying reason carry-over fixes are needed at all)
- I-00084 — stale origin/main ref breaks diff-coverage (one of the false-positive failures that triggered the S15 revert)
- I-00085 — `.mypy_cache/` triggers gitleaks false positives (the workflow ordering bug between S12 and S16)

When all four ship, the fix-cycle agent will be reliable enough that
operator-driven manual rescues should become rare.
