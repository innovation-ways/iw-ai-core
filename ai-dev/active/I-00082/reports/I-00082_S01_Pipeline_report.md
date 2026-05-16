# I-00082 S01 — Pipeline Report

**Work Item**: I-00082 — Fix-cycle agent has no allowed_paths enforcement  
**Step**: S01 (pipeline-impl)  
**Status**: Complete

## What Was Done

Implemented scope enforcement for the fix-cycle pipeline in `orch/daemon/fix_cycle.py`.

### Deliverables

1. **Scope section injected into fix-cycle prompts** — `_build_scope_block()` renders a `## Scope` section before "Errors to Address" in all three prompt builders (QV, browser, standard). When `allowed_paths` is empty, renders a "scope enforcement disabled" notice and skips reconciliation.

2. **Post-cycle scope reconciliation** — `_complete_fix_cycle()` now performs a set-diff between pre-cycle and post-cycle working-tree paths. Any file the agent touched (new or modified) that falls outside `allowed_paths + implicit_allows` is recorded as a violation. On violation: `FixCycle.status = FixStatus.escalated`, `fix_metadata["scope_violations"]` is populated, a `scope_violation_escalation` DaemonEvent is emitted. The agent's edits are preserved verbatim.

3. **Pre-cycle snapshot** — `attempt_fix_cycle()` calls `_captured_paths()` before launching the agent and stores the result in `fix_metadata["pre_cycle_paths"]`. This ensures operator pre-edits (files in `pre_cycle_paths`) are excluded from the violation set by the set-subtraction in `_complete_fix_cycle()`.

4. **Structured log line** — one INFO log line per cycle: `fix_cycle scope: item=... step=... cycle=... allowed=... in_scope=... out_of_scope=... violations=[...]`.

5. **`run_fix_cycle()` and `FixCycleResult`** — lightweight, DB-free entry point for tests. Injects `run_llm_agent` as a monkeypatch seam.

### Private helpers added

- `_scope_match(path, pattern)` — mirror of `executor/scope_gate.py:_matches()` (no import from executor/)
- `_implicit_allows(item_id)` — the three implicit globs (`ai-dev/active/`, `ai-dev/archive/`, `ai-dev/work/`)
- `_captured_paths(worktree)` — git diff + ls-files set
- `_load_allowed_paths(worktree_path, item_id)` — reads `scope.allowed_paths` from workflow-manifest.json
- `_build_scope_block(allowed)` — renders the prompt section

## Files Changed

- `orch/daemon/fix_cycle.py` — scope enforcement implementation
- `tests/integration/test_fix_cycle_scope_enforcement.py` — AC1 reproduction test (new file)

## Test Results

**TDD RED evidence** (before implementation):
```
tests/integration/test_fix_cycle_scope_enforcement.py::test_i00082_fix_cycle_escalates_on_out_of_scope_edit
— AttributeError: module 'orch.daemon.fix_cycle' has no attribute 'run_fix_cycle'
```

**TDD GREEN** (after implementation):
```
1 passed in 7.78s
```

## Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok (714 files already formatted) |
| `make type-check` | ok (no issues in 249 source files) |
| `make lint` | ok (all checks passed) |

## Notes

- `FixStatus.escalated` reused as-is; no new enum members added.
- Escalation does NOT count against the fix-cycle retry budget — callers that increment the budget must check `status != FixStatus.escalated`.
- AC3/AC4 tests will be added by S03 (tests-impl) on top of this file.
