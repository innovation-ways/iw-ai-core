# CR-00089: Fix-Cycle Pipeline Systemic Hardening (I-00113 RCA Follow-up)

**Type**: Change Request
**Priority**: High
**Reason**: Three systemic flaws identified in I-00113 root cause analysis cause items to loop indefinitely between needs_fix and scope-blocked states without operator intervention. These are independent of I-00113's specific fix and will recur on any future item.
**Created**: 2026-05-26
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This CR adds no database migrations. No Alembic revision is needed.

## Description

Three independent defects in the daemon's fix-cycle pipeline compound to create indefinite fix-cycle loops. This CR implements: (1) an `always_in_scope_paths` project config that prevents global files like `tests/assertion_free_baseline.txt` from triggering scope violations in any item, (2) a `completed_at` guard in `step_monitor.py` that prevents false crash-handling when `iw step-done` has already finalized a step, and (3) smarter cascade-reset logic in `fix_cycle.py` that skips resetting QV gates whose file-type coverage is irrelevant to what the fix cycle actually changed.

Reference: `ai-dev/active/I-00113/reports/I-00113_scope_blocked_root_cause_analysis.md`

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key locations: `orch/daemon/project_registry.py` (`ProjectConfig` dataclass), `orch/daemon/fix_cycle.py` (scope reconciliation + cascade reset), `orch/daemon/step_monitor.py` (crash handling).

## Current Behavior

### RC2 — Global files trigger scope violations

`_load_allowed_paths()` in `fix_cycle.py` reads only `scope.allowed_paths` from the item's `workflow-manifest.json`. Files outside that list trigger scope violations. Global project files like `tests/assertion_free_baseline.txt` are not item-specific and are never listed in an item's manifest — so any fix cycle that needs to update them is escalated as a scope violation and the item is permanently stuck until the operator manually adds the file to the manifest.

`ProjectConfig` in `project_registry.py` has no `always_in_scope_paths` field.

### RC1 belt-and-suspenders — No completed_at guard

In `_check_step_health()` in `step_monitor.py`, after the `_probe_for_child()` check (RC1 fix from I-00113), if no live child process is found, the code calls `_handle_crashed()` unconditionally. There is no check for whether `step_runs.completed_at` is already set — which would mean `iw step-done` already finalized the step cleanly. This `completed_at` guard would catch any edge case where the proc-scan misses a child that already exited normally.

### RC3 — Unconditional cascade reset

`_cascade_reset_upstream_qv_gates()` in `fix_cycle.py` resets ALL upstream QV gates (lint, format, typecheck, unit-tests, integration-tests, etc.) unconditionally whenever a fix cycle completes for any QV gate. It ignores what files the fix cycle actually changed. If a fix cycle only updated `tests/assertion_free_baseline.txt` (a text file), there is no reason to re-run lint, format, or typecheck — but the current code resets them all. This multiplies wall-clock time by 3-5x per fix cycle and, combined with RC1, creates feedback loops.

The function signature is:
```
_cascade_reset_upstream_qv_gates(db, cycle, failing_step, project_id) → list[str]
```
`cycle` is currently ignored (`ARG001` comment). `WorkflowStep.gate` (e.g., `"lint"`, `"typecheck"`, `"assertion-check"`) is available on every upstream gate record.

## Desired Behavior

### Fix 1 — always_in_scope_paths

`projects.toml` accepts a new `[projects.X.always_in_scope]` table with a `paths` list of glob patterns. These paths are parsed into `ProjectConfig.always_in_scope_paths: list[str]`.

In `fix_cycle.py`, the scope reconciliation logic appends `project_config.always_in_scope_paths` to the `allowed` list before computing violations. Files matching any pattern in `always_in_scope_paths` never trigger scope violations, for any item in the project, without needing to be declared in the item's manifest.

For iw-ai-core, the initial entry is `tests/assertion_free_baseline.txt`.

### Fix 2 — completed_at guard

In `_check_step_health()`, immediately before the call to `_handle_crashed()`, a new guard checks `run.completed_at is not None`. If set, the step already finished cleanly via `iw step-done` — crash handling is skipped and the function returns. This is belt-and-suspenders on top of `_probe_for_child()`.

### Fix 3 — Smarter cascade reset

`_cascade_reset_upstream_qv_gates()` gains a `changed_files: list[str]` parameter and a private `_GATE_RELEVANT_EXTENSIONS` dict mapping gate names to relevant file extensions:

```
lint            → {.py, .js, .ts, .css}
format          → {.py}
typecheck       → {.py}
unit-tests      → {.py}
integration-tests → {.py}
diff-coverage   → {.py}
assertion-check → {.py, .txt}
migration-check → {.py}
security-sast   → {.py}
```

A helper `_gate_is_relevant(gate_name, changed_files)` returns `True` if any changed file's extension is in the gate's relevant set, or conservatively `True` if `changed_files` is empty or the gate name is unknown. Only gates for which `_gate_is_relevant` returns `True` are reset. The `_peek_cascade_reset_ids()` mirror is updated with the same signature and logic.

The `changed_files` value is the output of the already-computed `_files_changed_by_fix_cycle()` call that exists in `_complete_fix_cycle()` (line ~1273). The caller passes it when invoking `_cascade_reset_upstream_qv_gates()`.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/daemon/project_registry.py` | `ProjectConfig` has no `always_in_scope_paths` | Adds `always_in_scope_paths: list[str]` field; parses from `projects.toml` |
| `projects.toml` | No `always_in_scope` table for any project | `iw-ai-core` project gets `[projects.iw-ai-core.always_in_scope]` with `paths` |
| `orch/daemon/fix_cycle.py` — scope reconciliation | Appends only manifest `allowed_paths` + implicit paths | Also appends `project_config.always_in_scope_paths` |
| `orch/daemon/fix_cycle.py` — cascade reset | Resets all upstream QV gates unconditionally | Filters by file-type relevance using `_GATE_RELEVANT_EXTENSIONS` |
| `orch/daemon/step_monitor.py` | No `completed_at` guard before `_handle_crashed` | Checks `run.completed_at is not None` first; skips crash handling if already finalized |

### Breaking Changes

None. All changes are additive or conservative:
- `always_in_scope_paths` defaults to empty list (no behavior change for projects that don't configure it).
- `completed_at` guard only prevents false crashes; it cannot suppress a real crash because `iw step-done` sets `completed_at` only on clean completion.
- Smarter cascade conservatively resets all gates when `changed_files` is empty or gate is unknown.

### Data Migration

None required. No schema changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | `always_in_scope_paths` in `ProjectConfig` + parse from `projects.toml`; update `projects.toml` for iw-ai-core | — |
| S02 | `backend-impl` | `fix_cycle.py` scope reconciliation: append `project_config.always_in_scope_paths` to allowed | after S01 |
| S03 | `backend-impl` | `step_monitor.py`: `completed_at` guard before `_handle_crashed` | parallel with S01 |
| S04 | `backend-impl` | `fix_cycle.py` cascade: `_GATE_RELEVANT_EXTENSIONS`, `_gate_is_relevant`, smarter reset | after S02 |
| S05 | `tests-impl` | Unit tests for all four changes | after S01–S04 |
| S06 | `code-review-impl` | Reviews S01–S05 | — |
| S07 | `code-review-final-impl` | Cross-agent final review | after S06 |
| S08 | `qv-gate` | lint | after S07 |
| S09 | `qv-gate` | format | after S07 |
| S10 | `qv-gate` | typecheck | after S07 |
| S11 | `qv-gate` | unit-tests | after S07 |
| S12 | `qv-gate` | integration-tests | after S07 |
| S13 | `self-assess-impl` | Self-assessment | after S12 |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00089_CR_Design.md` | Design | This document |
| `CR-00089_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00089_S01_Backend_prompt.md` | Prompt | always_in_scope_paths in ProjectConfig + projects.toml |
| `prompts/CR-00089_S02_Backend_prompt.md` | Prompt | fix_cycle.py scope reconciliation |
| `prompts/CR-00089_S03_Backend_prompt.md` | Prompt | step_monitor.py completed_at guard |
| `prompts/CR-00089_S04_Backend_prompt.md` | Prompt | fix_cycle.py smarter cascade reset |
| `prompts/CR-00089_S05_Tests_prompt.md` | Prompt | Unit tests for all four changes |
| `prompts/CR-00089_S06_CodeReview_prompt.md` | Prompt | Per-agent code review |
| `prompts/CR-00089_S07_CodeReview_Final_prompt.md` | Prompt | Cross-agent final review |
| `prompts/CR-00089_S13_SelfAssess_prompt.md` | Prompt | Self-assessment |

## Acceptance Criteria

### AC1: always_in_scope prevents scope violations for global files

```
Given a project has always_in_scope.paths = ["tests/assertion_free_baseline.txt"] in projects.toml
When a fix cycle modifies tests/assertion_free_baseline.txt and nothing else in the allowed list
Then the scope reconciliation does not raise a scope violation and the fix cycle completes normally
```

### AC2: always_in_scope paths not in manifest are transparent

```
Given an item's workflow-manifest.json has no mention of tests/assertion_free_baseline.txt
When fix_cycle.py loads allowed paths for that item
Then the result includes tests/assertion_free_baseline.txt via project_config.always_in_scope_paths
```

### AC3: completed_at guard prevents false crash on already-finalized step

```
Given a step_run has completed_at set (iw step-done was already called)
When _check_step_health is called and _is_pid_alive returns False and _probe_for_child returns False
Then _handle_crashed is NOT called and the function returns early
```

### AC4: Smarter cascade skips irrelevant gates for non-Python changes

```
Given a fix cycle changed only tests/assertion_free_baseline.txt (extension .txt)
When _cascade_reset_upstream_qv_gates is called with changed_files=["tests/assertion_free_baseline.txt"]
Then upstream "lint", "format", "typecheck" gates are NOT reset
And the upstream "assertion-check" gate IS reset (if present and completed)
```

### AC5: Smarter cascade is conservative when changed_files is empty

```
Given a fix cycle has changed_files=[]
When _cascade_reset_upstream_qv_gates is called
Then all upstream completed QV gates are reset (existing behavior preserved)
```

### AC6: projects.toml parsing is non-breaking for existing projects

```
Given a project entry in projects.toml with no always_in_scope table
When ProjectConfig is constructed from that entry
Then always_in_scope_paths defaults to [] and no error is raised
```

## Rollback Plan

- **Database**: Not applicable (no migrations)
- **Code**: `git revert` the squash-merge commit; all changes are in three Python files and `projects.toml`
- **Data**: No data loss on rollback

## Dependencies

- **Depends on**: I-00113 (RC1 proc-scan fix already in main — `23561e95`; this CR adds the belt-and-suspenders guard)
- **Blocks**: None

## Impacted Paths

- `orch/daemon/project_registry.py`
- `projects.toml`
- `orch/daemon/fix_cycle.py`
- `orch/daemon/step_monitor.py`
- `tests/unit/daemon/test_always_in_scope.py`
- `tests/unit/daemon/test_step_monitor_completed_at_guard.py`
- `tests/unit/daemon/test_cascade_smarter_scope.py`
- `orch/daemon/batch_manager.py` *(conditional — only if S02 needs to thread `project_config` through the `run_fix_cycle` call site)*

## TDD Approach

- **Unit tests**: Three new test files covering (a) always_in_scope scope check, (b) completed_at guard, (c) smarter cascade filter. Each uses the existing unit-test patterns from `tests/unit/daemon/` (see `test_scope_overlap.py`, `test_step_monitor_i00113_probe_unit.py`, `test_fix_cycle_budget_exemption.py` for fixture patterns).
- **Integration tests**: No new integration tests required — the changes are in pure-logic functions that do not need a database. Existing `make test-integration` covers the surrounding machinery.
- **Updated tests**: None expected — the changes are additive. If any existing test breaks (e.g., a test that asserts `_cascade_reset_upstream_qv_gates` always resets all gates), update the assertion to match the new behavior.

## Notes

- S03 (step_monitor.py) is independent of S01/S02 and can run in parallel with S01.
- S04 (cascade smarter scope) depends on S02 to confirm fix_cycle.py structure is stable before adding the second change to the same file.
- The `_GATE_RELEVANT_EXTENSIONS` mapping is intentionally conservative: unknown gate names fall back to `{".py"}`, which means `.py` changes reset unknown gates (same as today). Only non-Python-only changes get targeted filtering.
- `_peek_cascade_reset_ids()` is a mirror of `_cascade_reset_upstream_qv_gates` used by the thrashing detector. It must receive the same `changed_files` parameter and apply the same filter, otherwise the thrashing detector will preview a different reset-set than what actually executes.
