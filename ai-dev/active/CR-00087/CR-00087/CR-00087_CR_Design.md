# CR-00087: Auto-amend scope violations matching per-project allow-patterns

**Type**: Change Request
**Priority**: Medium
**Reason**: Operator friction — the "✎ Amend scope" click adds no judgment value for routine, mechanical out-of-scope edits (test files, docs, ai-dev artefacts) yet blocks the work item until clicked. Eliminating it for pre-blessed paths is a quality-of-life improvement that compounds across many work items.
**Created**: 2026-05-25
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This CR adds no migrations.)

## Description

Add a per-project `auto_amend_scope` config in `.iw-orch.json` that lets the daemon automatically apply the same amend-and-restart that the operator does today, gated by an allow-pattern filter (e.g. `tests/**`, `**/*.md`, `docs/**`, `ai-dev/**`) plus an optional `max_paths` safety cap. Field absent → behaviour identical to today (opt-in by design). When every violated path matches the allow-patterns and the count stays within `max_paths`, the daemon runs `amend_allowed_paths()` inline in `_complete_fix_cycle`, emits a new `scope_auto_amended` event (alongside the existing `scope_violation_escalation`), creates a new `StepRun`, and transitions the step back to `pending` without the badge ever appearing in the UI.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.

This CR sits inside the daemon's fix-cycle subsystem introduced by I-00082 (scope enforcement) and I-00101 (scope-blocked badge + amend modal). The amend helper (`amend_allowed_paths`) is reused as-is, and the violation detector's matcher (`_scope_match` in `orch/daemon/fix_cycle.py` — promoted to public `scope_match` by this CR) is shared with the new auto-amend filter so the two layers cannot disagree on pattern semantics. Nothing in this CR replaces existing behaviour — the manual click remains available when violations don't match the allow-patterns.

## Current Behavior

When a fix-cycle agent in `orch/daemon/fix_cycle.py:_complete_fix_cycle` (function defined at ~line 1043; escalation branch at ~line 1117) detects that the agent touched files outside `scope.allowed_paths`:

1. `FixCycle.status` is set to `escalated`.
2. `FixCycle.fix_metadata.scope_violations` is populated with the list of out-of-scope paths.
3. `WorkflowStep.status` is set to `needs_fix`.
4. A `scope_violation_escalation` DaemonEvent is emitted.
5. The dashboard's steps-table fragment (`fragments/item_steps_table.html:114-118`) renders a yellow **scope_blocked** badge and exposes a "✎ Amend scope" / "Revert" / "Skip" trio (~line 215).
6. The work item is now blocked on a human click.

When the operator clicks "✎ Amend scope":

7. `dashboard/routers/actions.py:444` (`POST /…/scope/amend-and-restart/{step_id}`) validates the latest cycle is escalated with scope_violations and that requested paths are a subset of the violations.
8. `amend_allowed_paths()` (`orch/daemon/scope_amendment.py:57`) appends the paths to `scope.allowed_paths` in both the worktree's `workflow-manifest.json` and the parent design-time copy (deduplicating).
9. A `scope_amended_by_operator` DaemonEvent is emitted.
10. A new `StepRun` is created (mirroring the last run), and the step is transitioned `needs_fix` → `pending`. The daemon will pick it up on the next poll.

In practice, the violated paths are almost always things like `tests/test_something.py` (agent added companion test), `docs/IW_AI_Core_XXX.md` (small doc touch), or `ai-dev/active/<ID>/...` (artefact write) — paths the project considers low-risk and would always approve. The mandatory click is friction without value.

## Desired Behavior

After this CR ships, projects may add an `auto_amend_scope` block to `.iw-orch.json`:

```jsonc
{
  "auto_amend_scope": {
    "auto_allow_patterns": [
      "tests/**",
      "**/*.md",
      "docs/**",
      "ai-dev/**"
    ],
    "max_paths": 10
  }
}
```

When the block is **absent**, behaviour is identical to today.

When the block is **present**, the new flow inside `_complete_fix_cycle` is:

1. Detect violations (unchanged).
2. Set `FixCycle.status = escalated`, populate `fix_metadata.scope_violations`, set `WorkflowStep.status = needs_fix`, emit `scope_violation_escalation` (unchanged — preserves audit trail).
3. **New**: evaluate `should_auto_amend(violations, project_config.auto_amend_allow_patterns, project_config.auto_amend_max_paths)`. The helper returns `True` only when:
   - The allow-patterns list is non-empty (feature off when empty).
   - `len(violations) <= max_paths` (when `max_paths` is `None`, no cap is applied).
   - **Every** violation matches **some** allow-pattern via the **same matcher used by the violation detector itself** — `_scope_match` from `orch/daemon/fix_cycle.py` (handles `prefix/**` + plain `fnmatch`). Using the same matcher guarantees that no path can be classified as a violation but rejected by the auto-amend filter (or vice versa) because of pattern-semantics skew.
4. On `True`:
   - Call `amend_allowed_paths(worktree_path, item_id, list(violations))` — same helper the operator endpoint uses.
   - Emit a new `scope_auto_amended` DaemonEvent (distinct event type so observers can distinguish auto vs. manual).
   - Create a new `StepRun` mirroring the last one (run_number incremented, command/worktree_path/cli_tool/timeout copied).
   - Set `WorkflowStep.status = pending`, clear `started_at`/`completed_at`.
   - Log a daemon INFO line summarising the auto-amend.
5. On `False`: leave the step in `needs_fix` — today's manual flow remains untouched.

The yellow scope_blocked badge therefore stops appearing for matched violations in practice: the auto-amend block runs synchronously inside `_complete_fix_cycle`, completing in well under a second between the escalation commit and the amend commit. The dashboard's poll interval is far longer than this window, so the badge is never observed by an operator. (Strictly speaking the two state changes are in separate transactions, not a single one — see Notes for the rationale and the cost of merging them.)

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `ProjectConfig` (in-memory) | No auto-amend fields | New `auto_amend_allow_patterns: list[str]` (default `[]` → off) and `auto_amend_max_paths: int \| None` (default `None`) fields |
| `.iw-orch.json` schema | No `auto_amend_scope` key | New optional `auto_amend_scope: { auto_allow_patterns: [...], max_paths: N }` block |
| `orch/daemon/scope_amendment.py` | `amend_allowed_paths` / `revert_paths_in_worktree` / `latest_scope_violation` | Adds pure `should_auto_amend(violations, allow_patterns, max_paths) -> bool` |
| `orch/daemon/fix_cycle.py:_complete_fix_cycle` | Escalation branch sets `cycle.status = escalated` + `step.status = needs_fix`, emits `scope_violation_escalation`, returns | Same as before, then if `should_auto_amend` is `True`: call `amend_allowed_paths`, emit `scope_auto_amended`, create new `StepRun`, set step → `pending` |
| DaemonEvent types | `scope_violation_escalation`, `scope_amended_by_operator`, `scope_reverted_by_operator` | New type `scope_auto_amended` |
| Dashboard UI | scope_blocked badge appears, operator clicks Amend | Same UI; the badge simply does not appear for auto-amended paths (step transitions out of `needs_fix` before any UI poll picks it up) |

### Breaking Changes

- **None.** Feature is opt-in. Projects without `auto_amend_scope` see zero behavioural change.

### Data Migration

- **None.** No schema changes, no row mutations. Pure code change reading new optional JSON keys at daemon load time.
- Reversibility: removing `auto_amend_scope` from `.iw-orch.json` + reloading the daemon (`./ai-core.sh daemon reload`) returns the project to the manual-click flow.

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern (one module or closely-related file group). Split multi-concern work across multiple steps. See `skills/iw-workflow/SKILL.md` for the canonical rule.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Parse `auto_amend_scope` in `orch/daemon/project_registry.py`; add `ProjectConfig.auto_amend_allow_patterns` + `auto_amend_max_paths` fields with malformed-input tolerance | — |
| S02 | backend-impl | Add pure `should_auto_amend(violations, allow_patterns, max_paths)` helper to `orch/daemon/scope_amendment.py`, reusing the violation detector's matcher (`_scope_match` from `orch/daemon/fix_cycle.py`) for semantic consistency | — |
| S03 | backend-impl | Hook auto-amend inline into `orch/daemon/fix_cycle.py:_complete_fix_cycle` after the escalation branch; emit `scope_auto_amended`, create new `StepRun`, set step → `pending` | — |
| S04 | tests-impl | Extend `tests/integration/test_scope_amend_endpoints.py` with positive + negative auto-amend integration tests (manifest update, both events emitted, step transitions, no manifest update on no-match) | — |
| S05 | code-review-impl | Per-agent code review of S01–S04 | — |
| S06 | code-review-final-impl | Cross-agent final review | — |
| S07 | qv-gate (lint) | `make lint` | — |
| S08 | qv-gate (format) | `make format` | — |
| S09 | qv-gate (typecheck) | `make typecheck` | — |
| S10 | qv-gate (unit-tests) | `make test-unit` | — |
| S11 | qv-gate (integration-tests) | `make test-integration` | — |
| S12 | self-assess-impl | Self-assessment via `iw-item-analyze` (project flag `self_assess = true`) | — |

Agent slugs: `database-impl`, `backend-impl`, `api-impl`, `frontend-impl`, `tests-impl`, `pipeline-impl`, `template-impl`, `self-assess-impl`. Fix cycles for failed `code-review-impl` / `code-review-final-impl` runs are handled automatically by the daemon's fix-cycle protocol — they are not declared as separate manifest steps (matching project convention; see CR-00080..CR-00085).

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — pure code change

### API Changes

- **New endpoints**: None (the manual operator endpoint stays unchanged)
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None — the scope_blocked badge and amend modal are unchanged; they simply stop appearing for auto-amended violations because the step transitions out of `needs_fix` before any UI poll observes it.
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00087/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00087_CR_Design.md` | Design | This document |
| `CR-00087_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00087_S01_BackendImpl_prompt.md` | Prompt | S01 — registry parsing |
| `prompts/CR-00087_S02_BackendImpl_prompt.md` | Prompt | S02 — `should_auto_amend` helper |
| `prompts/CR-00087_S03_BackendImpl_prompt.md` | Prompt | S03 — fix_cycle integration |
| `prompts/CR-00087_S04_TestsImpl_prompt.md` | Prompt | S04 — integration tests |
| `prompts/CR-00087_S05_CodeReview_prompt.md` | Prompt | S05 — per-agent code review |
| `prompts/CR-00087_S06_CodeReview_Final_prompt.md` | Prompt | S06 — final cross-agent review |
| `prompts/CR-00087_S12_SelfAssess_prompt.md` | Prompt | S12 — self-assessment |

Reports are created during execution in `ai-dev/work/CR-00087/reports/`.

## Acceptance Criteria

### AC1: Feature is off by default

```
Given a project whose .iw-orch.json has no auto_amend_scope key
When a fix-cycle agent commits an out-of-scope edit and _complete_fix_cycle runs
Then the FixCycle is escalated, the step is set to needs_fix, scope_violation_escalation is emitted,
  and no scope_auto_amended event is emitted,
  and the step remains in needs_fix until an operator clicks Amend or Revert
```

### AC2: Auto-amend fires when every violation matches allow-patterns

```
Given a project with auto_amend_scope.auto_allow_patterns = ["tests/**", "**/*.md"] and max_paths = 10
And a fix cycle that produced violations = ["tests/unit/test_foo.py", "docs/notes.md"]
When _complete_fix_cycle runs
Then FixCycle.status is set to escalated AND scope_violation_escalation is emitted (audit preserved)
And amend_allowed_paths is called with the violation list
And both the worktree manifest and the parent manifest have those paths appended to scope.allowed_paths
And a scope_auto_amended DaemonEvent is emitted with the matched paths and patterns
And a new StepRun is created with run_number = previous + 1, mirroring command/worktree_path/cli_tool/timeout
And WorkflowStep.status is pending, started_at and completed_at are None
```

### AC3: Auto-amend does NOT fire when any violation falls outside allow-patterns

```
Given a project with auto_amend_scope.auto_allow_patterns = ["tests/**"]
And a fix cycle that produced violations = ["tests/unit/test_foo.py", "orch/daemon/fix_cycle.py"]
When _complete_fix_cycle runs
Then FixCycle.status is set to escalated and scope_violation_escalation is emitted (today's behaviour)
And amend_allowed_paths is NOT called
And no scope_auto_amended event is emitted
And WorkflowStep.status is needs_fix (the operator must intervene)
```

### AC4: Auto-amend respects max_paths cap

```
Given a project with auto_amend_scope.auto_allow_patterns = ["tests/**"] and max_paths = 3
And a fix cycle that produced 5 violations all under tests/
When _complete_fix_cycle runs
Then auto-amend is NOT fired (count exceeds cap)
And the step is left in needs_fix
```

### AC5: Malformed config falls back to off

```
Given a project whose .iw-orch.json has auto_amend_scope set to a non-dict value (e.g. an array, a string, or null)
Or whose auto_allow_patterns contains non-string entries
When the daemon loads the project config
Then the malformed block is logged at WARNING level
And the project's auto_amend_allow_patterns is treated as []
And auto-amend never fires for this project
```

### AC6: Audit trail is preserved

```
Given an auto-amend has fired
When an operator inspects the DaemonEvents feed for this work item
Then they see BOTH scope_violation_escalation (cause) AND scope_auto_amended (action)
And the scope_auto_amended payload contains step_id, added_paths, manifests_updated, matched_patterns
```

## Rollback Plan

- **Database**: N/A — no schema change.
- **Code**: Revert the merge commit, or remove `auto_amend_scope` from each project's `.iw-orch.json` and reload the daemon (`./ai-core.sh daemon reload`). The latter is a runtime-only rollback that needs no redeploy.
- **Data**: No data loss possible. The auto-amend writes are identical to the manual operator amend — they only ever append paths to `scope.allowed_paths` and create new `StepRun` rows. To "undo" an auto-amend after the fact, edit the workflow-manifest.json by hand (same as today's manual amend rollback).

## Dependencies

- **Depends on**: None. Self-contained.
- **Blocks**: None.

## Impacted Paths

- `orch/daemon/project_registry.py`
- `orch/daemon/scope_amendment.py`
- `orch/daemon/fix_cycle.py`
- `docs/IW_AI_Core_Daemon_Design.md`
- `.iw-orch.json`
- `tests/unit/daemon/test_project_registry_auto_amend_scope.py`
- `tests/unit/daemon/test_scope_amendment.py`
- `tests/unit/test_fix_cycle.py`
- `tests/integration/test_scope_amend_endpoints.py`

## TDD Approach

- **Unit tests** (S01–S02):
  - `should_auto_amend` matrix in `tests/unit/daemon/test_scope_amendment.py`: empty allow-patterns → False; allow-patterns present + all violations match → True; partial match → False; over `max_paths` → False; `max_paths=None` skips the cap; matcher behaviour mirrors `_scope_match` from `orch/daemon/fix_cycle.py` (handles `prefix/**` + plain `fnmatch`) so the auto-amend filter cannot disagree with the violation detector.
  - Registry parsing in a NEW file `tests/unit/daemon/test_project_registry_auto_amend_scope.py` (per-concern split mirrors the existing `test_project_registry_overlap_gate.py`): `auto_amend_scope` absent → defaults; valid block → parsed; malformed (non-dict, non-list patterns, non-string pattern entries, non-int max_paths) → defaults + WARNING; `max_paths` absent → `None`.
- **Integration tests** (S04):
  - In `tests/integration/test_scope_amend_endpoints.py`: positive test — seed a worktree manifest with `scope.allowed_paths`, write a real workflow-manifest.json on disk via a tmp_path fixture, seed an escalated FixCycle with violations that all match the project's `auto_allow_patterns`, drive `_complete_fix_cycle`, assert the manifest is updated, the StepRun is created, the step is `pending`, and BOTH `scope_violation_escalation` + `scope_auto_amended` events appear.
  - Negative test — same setup but with a violation that falls outside the allow-patterns; assert no manifest update, no `scope_auto_amended` event, step stays `needs_fix`.
- **Updated tests**: existing tests in `tests/unit/daemon/test_scope_amendment.py` and `tests/integration/test_scope_amend_endpoints.py` continue to pass (no behaviour change for projects without the new config). S03 adds a small short-circuit unit test for the new `_try_auto_amend_after_escalation` helper in `tests/unit/test_fix_cycle.py` (matching the project's existing per-concern fix-cycle unit test location).

## Notes

- **Why preserve `scope_violation_escalation` even when auto-amend fires?** Two reasons. (1) Operators auditing why a path was added to `allowed_paths` need to see that it was caused by a real scope violation — without the escalation event, the auto-amend looks like a spontaneous manifest edit. (2) Keeping the escalation event keeps the daemon's exit path identical regardless of auto-amend; the auto-amend is layered on top, not woven into the existing branch, which is easier to reason about and easier to revert.
- **Why inline in `_complete_fix_cycle` instead of a separate poller pass?** Decided in the design conversation: inline avoids the yellow badge flicker (badge would appear for one poll cycle then disappear). The auto-amend block runs in a second DB transaction inside the same function call — the two-commit gap is sub-second and well below the dashboard's poll interval, so the badge is not observed in practice. Merging the escalation and auto-amend writes into a single transaction was considered and rejected: the escalation commit is load-bearing (it must persist even when auto-amend doesn't fire), and rearranging the existing branch to defer that commit would complicate the recovery semantics for projects that don't opt in. The trade-off of two commits is acceptable; the auto-amend block is extracted into a clearly-named helper function (`_try_auto_amend_after_escalation`) so the body of `_complete_fix_cycle` stays readable.
- **Why allow-pattern filter rather than blanket boolean?** Decided in the design conversation: blanket "auto-accept everything" effectively removes the scope gate. The allow-pattern filter preserves the gate's value for unexpected sprawl (e.g. a docs-only item touching `orch/daemon/`) while killing the noise for the routine cases.
- **Match function reuse**: `should_auto_amend` MUST use the same matcher the violation detector uses — `_scope_match` from `orch/daemon/fix_cycle.py`. Using a different matcher (e.g. the richer `_matches` in `scope_overlap.py`) could create edge cases where a path is detected as a violation but rejected by the auto-amend filter (or vice versa) because the two matchers interpret patterns differently. To reuse the function cleanly, S02 should promote `_scope_match` to a public name (e.g. `scope_match`) — keep `_scope_match` as a thin backward-compat alias if anything else in `fix_cycle.py` still references it — and import the public name into `scope_amendment.py`. Do NOT duplicate the matcher body.
- **Revert flow remains manual**, by design: reverting agent edits is destructive (rewrites the working tree); the operator should always make that call.
