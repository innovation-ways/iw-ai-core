# CR-00088: Auto-merge — partial-allowlist semantics in Phase 1 dry-run

**Type**: Change Request
**Priority**: Medium
**Reason**: Cross-batch rebase conflicts that mix allowlisted (.md tracker) and non-allowlisted (Makefile, pyproject.toml) files today get `skipped_reason="not_allowlisted"` and no LLM is invoked for anything — even though the allowlisted files were eligible. CR-00084 hit this on 2026-05-25.
**Created**: 2026-05-25
**Status**: Draft

---

## ⛔ Docker is off-limits

No Docker operations. Testcontainer fixtures in integration tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This CR adds no Alembic migrations. `DaemonEvent.metadata` schema is JSONB and extensible without DDL.

## Description

Change `classify_conflicts()` from all-or-nothing allowlist matching to partition semantics: matching files go to the LLM (still dry-run = proposed only, never applied to the worktree in Phase 1), non-matching files are surfaced to the operator as `deferred_files` in the daemon event metadata. Refuse-list still wins outright and is unchanged.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The auto-merge subsystem lives in `orch/daemon/auto_merge.py` (classification, LLM invocation, event emission), is called from `orch/daemon/merge_queue.py` (when `worktree_commit.sh` reports rebase conflicts), and is gated by `executor/auto_merge.toml` (`phase`, allowlist, refuselist, limits). Phase ladder is described in R-00076 and in `executor/auto_merge.toml`'s top comment block. Tracker: `ai-dev/active/AUTO_MERGE_RESOLUTION.md`.

## Current Behavior

`orch/daemon/auto_merge.py:classify_conflicts()` step 6 (`# 6. Allowlist check`, lines ~485–499) computes the set of conflicted files whose path matches none of the configured `allowlist_patterns`. If that set is non-empty, it returns a `ClassificationResult(skipped_reason="not_allowlisted", eligible_files=())` — i.e., zero files are passed to the LLM. The caller in `orch/daemon/merge_queue.py` (lines ~512–527) then emits `EVENT_AUTO_RESOLUTION_SKIPPED` with `{"reason": "not_allowlisted", "eligible_files": [...the full original list...]}` and the merge falls through to `merge_failed`. The operator gets no LLM proposal for any file, even those that were allowlisted.

Concrete impact on 2026-05-25: CR-00084 had rebase conflicts in `Makefile`, `ai-dev/work/TESTS_ENHANCEMENT.md`, `pyproject.toml`. `**/*.md` is in `executor/auto_merge.toml`'s `[allowlist].patterns`, so the .md file was eligible. `Makefile` and `pyproject.toml` were not. Today's behaviour skipped all three. CR-00082 (only .md conflicts that same evening) WAS attempted (Phase 1 dry-run proposed 2 resolutions) — confirming the LLM path itself works; only the all-or-nothing gate prevented CR-00084 from also benefiting.

## Desired Behavior

`classify_conflicts()` partitions the input `conflict_files` into two disjoint sets:

- `eligible_files`: those that match `allowlist_patterns` AND survive all the earlier gates (refuse-list, binary, file-too-large, hunk-too-large, too-many-files).
- `deferred_files`: those that fail only the allowlist check (and survived every earlier gate).

If `eligible_files` is non-empty, the LLM is invoked for that subset; if `deferred_files` is also non-empty, the daemon event records both subsets so the operator knows exactly which files still need manual resolution. The `merge_failed` outcome is unchanged — Phase 1 never modifies the worktree, so the operator still rebases manually; the value is that they now have LLM proposals to copy in for the allowlisted subset, dramatically narrowing the file count they must resolve from scratch.

If `eligible_files` is empty after partitioning (i.e., every conflicted file is non-allowlisted), behaviour is unchanged from today: emit `EVENT_AUTO_RESOLUTION_SKIPPED` with `reason="not_allowlisted"` (now including the explicit list of deferred files for operator clarity).

If `eligible_files` is non-empty AND `deferred_files` is non-empty (the partial case), emit `EVENT_AUTO_RESOLUTION_ATTEMPTED` with the existing `phase`, `conflict_files`, `policy_decision`, `runtime_option_id` keys, PLUS two new keys: `allowlisted_files` (alias for `eligible_files`) and `deferred_files`. The subsequent `EVENT_AUTO_RESOLVED` event's metadata gets the same two new keys.

The refuse-list precedence is **unchanged**: if any conflicted file matches `refuselist_patterns`, the whole resolution still aborts with `skipped_reason="refuse_list"`. Defence in depth wins over partial progress.

Phase remains 1 (dry-run). No worktree mutation. No change to `_DEFAULT_ALLOWLIST`. No change to the limits (`max_conflict_hunk_lines`, `max_conflicted_files_per_merge`, `max_file_size_bytes`).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `classify_conflicts()` in `orch/daemon/auto_merge.py` | Returns `ClassificationResult(eligible_files=(), skipped_reason="not_allowlisted")` when any file is non-allowlisted | Returns `ClassificationResult(eligible_files=<matching subset>, deferred_files=<non-matching subset>, skipped_reason=None)` when at least one file is allowlisted; only sets `skipped_reason="not_allowlisted"` when zero files match |
| `ClassificationResult` dataclass | Fields: `eligible_files, refuse_files, oversized_files, oversized_hunks, binary_files, skipped_reason` | Adds `deferred_files: tuple[str, ...] = ()` |
| `EVENT_AUTO_RESOLUTION_ATTEMPTED` metadata in `attempt_resolution()` | `{phase, conflict_files, policy_decision, runtime_option_id}` | Adds `allowlisted_files`, `deferred_files` |
| `EVENT_AUTO_RESOLVED` metadata | `{phase, proposed_files, abstained_files, error_files, llm_calls_summary}` | Adds `deferred_files` |
| `EVENT_AUTO_RESOLUTION_FAILED` metadata in `attempt_resolution()` | `{phase, abstained_files, error_files, proposed_files, runtime_option_id, total_input_tokens, total_output_tokens, per_file_errors}` | Adds `deferred_files` (so the operator sees the full partial-allowlist picture even when the LLM abstains/errors for every eligible file) |
| `EVENT_AUTO_RESOLUTION_SKIPPED` metadata in `merge_queue.py` partial-skip path | `{reason, eligible_files, refuse_files, binary_files, oversized_files, oversized_hunks}` | Adds `deferred_files` (already-listed `eligible_files` keeps the original full list for backward compat) |
| `executor/worktree_commit.sh` rebase-conflict error message | Lists every conflicted file under "Rebase conflicts detected" | Unchanged. The bash script does not consume `deferred_files` (the partition happens later in Python). |

### Breaking Changes

None for external callers. Internal `ClassificationResult` adds a new field with a default — all existing constructors still work. Event metadata adds new keys; existing consumers (dashboard auto-merge views) ignore unknown keys.

### Data Migration

None. `DaemonEvent.metadata` is JSONB and the new keys are additive.

## Implementation Plan

### Agents and Execution Order

> Step-granularity rule: each implementation step targets one cohesive concern.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Partition logic in `classify_conflicts()` + add `deferred_files` to `ClassificationResult` + update unit tests in `tests/unit/test_auto_merge_classifier.py` (RED-first: add failing tests for the partial-allowlist case, all-deferred case, refuselist-wins-over-partial case before changing production code) | — |
| S02 | backend-impl | Event-emission integration in `orch/daemon/auto_merge.py:attempt_resolution()` (add `allowlisted_files`, `deferred_files` to `EVENT_AUTO_RESOLUTION_ATTEMPTED` + `EVENT_AUTO_RESOLVED` + `EVENT_AUTO_RESOLUTION_FAILED` metadata) AND in `orch/daemon/merge_queue.py` (add `deferred_files` to the skipped-event metadata + thread `deferred_files` through from `classify_conflicts`); new integration tests + a tightened skipped-event assertion in `tests/integration/test_auto_merge_phase1.py` | — |
| S03 | tests-impl | Integration test in `tests/integration/test_auto_merge_phase1.py` (or new `tests/integration/test_auto_merge_partial_allowlist.py`) reproducing the CR-00084 conflict shape: 3 conflicted files where 1 matches allowlist; assert event metadata partitions correctly and refuselist-wins still holds | — |
| S04 | CodeReview | Per-agent review of S01+S02+S03 implementation against the design doc | — |
| S05 | CodeReview_Final | Global cross-agent review | — |
| S06–S13 | qv-gate | lint, assertions, format-check, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S14 | self-assess-impl | Self-assessment via iw-item-analyze skill (project has `self_assess = true`) | — |

No browser_verification step — daemon-internal logic, no UI surface.

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
- **Modified components**: None (existing dashboard auto-merge event detail views ignore unknown JSON keys; rendering the new `deferred_files` is a follow-up if/when the operator wants it surfaced)
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00088_CR_Design.md` | Design | This document |
| `CR-00088_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00088_S01_Backend_prompt.md` | Prompt | Partition logic + RED-first classifier tests |
| `prompts/CR-00088_S02_Backend_prompt.md` | Prompt | Event-emission integration |
| `prompts/CR-00088_S03_Tests_prompt.md` | Prompt | Integration test reproducing CR-00084 shape |
| `prompts/CR-00088_S04_CodeReview_prompt.md` | Prompt | Per-agent review |
| `prompts/CR-00088_S05_CodeReview_Final_prompt.md` | Prompt | Final cross-agent review |
| `prompts/CR-00088_S14_SelfAssess_prompt.md` | Prompt | Post-execution self-assessment |

## Acceptance Criteria

### AC1: Partial-allowlist partitions correctly

```
Given a rebase conflict spanning three files: docs/foo.md, Makefile, pyproject.toml
And the active config has allowlist_patterns=["**/*.md"]
And no file matches refuselist_patterns
When classify_conflicts() runs
Then ClassificationResult.eligible_files == ("docs/foo.md",)
And ClassificationResult.deferred_files == ("Makefile", "pyproject.toml")
And ClassificationResult.skipped_reason is None
```

### AC2: All-deferred still emits the existing skip event

```
Given a rebase conflict spanning two files: Makefile, pyproject.toml
And the active config has allowlist_patterns=["**/*.md"]
When classify_conflicts() runs
Then ClassificationResult.eligible_files == ()
And ClassificationResult.deferred_files == ("Makefile", "pyproject.toml")
And ClassificationResult.skipped_reason == "not_allowlisted"
And the daemon emits EVENT_AUTO_RESOLUTION_SKIPPED with metadata.reason="not_allowlisted" and metadata.deferred_files==["Makefile","pyproject.toml"]
```

### AC3: Refuse-list still wins over partial allowlist

```
Given a rebase conflict spanning three files: docs/foo.md, orch/db/migrations/versions/abc.py, Makefile
And the active config has allowlist_patterns=["**/*.md"] and refuselist_patterns=["orch/db/migrations/versions/*.py"]
When classify_conflicts() runs
Then ClassificationResult.eligible_files == ()
And ClassificationResult.deferred_files == ()
And ClassificationResult.refuse_files == ("orch/db/migrations/versions/abc.py",)
And ClassificationResult.skipped_reason == "refuse_list"
```

### AC4: Phase-1 dry-run still never mutates the worktree

```
Given a partial-allowlist rebase conflict (some files eligible, some deferred)
And phase == 1
When attempt_resolution() completes
Then the worktree's working tree contents are byte-for-byte identical to before the call
And EVENT_AUTO_RESOLVED.metadata.phase == 1
And EVENT_AUTO_RESOLVED.metadata.deferred_files == [...the deferred subset...]
And worktree_commit.sh continues to abort the rebase as today
```

### AC5: Integration test reproducing CR-00084 shape

```
Given an integration test that creates a worktree with rebase conflicts in {Makefile, docs/foo.md, pyproject.toml}
And the project config has the default allowlist (which includes **/*.md)
When the daemon polls the merge queue
Then EVENT_AUTO_RESOLUTION_ATTEMPTED is emitted with event_metadata["allowlisted_files"]==["docs/foo.md"] and event_metadata["deferred_files"]==["Makefile","pyproject.toml"]
And EVENT_AUTO_RESOLVED is emitted (dry-run) with the LLM proposal for docs/foo.md (or a stub if no API key)
And the work item ends in status="failed" (unchanged Phase-1 behaviour)
```

### AC6: FAILED event surfaces the deferred subset even on LLM abstain/error

```
Given a partial-allowlist rebase conflict (some files eligible, some deferred)
And the LLM abstains or errors for every eligible file
When attempt_resolution() emits EVENT_AUTO_RESOLUTION_FAILED
Then EVENT_AUTO_RESOLUTION_FAILED.event_metadata["deferred_files"] == <the deferred subset>
And EVENT_AUTO_RESOLUTION_FAILED.event_metadata["abstained_files"] reflects the eligible-but-abstained files
And the work item still ends in status="failed" (Phase-1 behaviour unchanged)
```

## Rollback Plan

- **Database**: Not applicable.
- **Code**: Single revert commit of the merge SHA. `executor/auto_merge.toml` was not changed by this CR; refuse-list precedence is unchanged; phase stays at 1 — all existing behaviour for the all-allowlisted and all-deferred cases is preserved bit-for-bit.
- **Data**: Daemon events are append-only; no loss.

## Dependencies

- **Depends on**: None
- **Blocks**: The Phase-2 promotion CR (to be filed separately as the follow-up). That CR cannot land safely until this one has run in dry-run on real conflicts long enough for the operator to eyeball the partial-allowlist proposals in `daemon_events`.

## Impacted Paths

- `orch/daemon/auto_merge.py`
- `orch/daemon/merge_queue.py`
- `tests/unit/test_auto_merge_classifier.py`
- `tests/integration/test_auto_merge_phase1.py`
- `tests/integration/test_auto_merge_partial_allowlist.py`
- `docs/research/R-00076-llm-automated-merge-resolution.md`
- `ai-dev/active/AUTO_MERGE_RESOLUTION.md`

(Note: S02's new tests live in `tests/integration/test_auto_merge_phase1.py`, NOT in `tests/unit/test_auto_merge_invoke.py` — they read `DaemonEvent` rows after `attempt_resolution()` commits, which requires a real testcontainer DB session. Mocking the DB is forbidden per CLAUDE.md.)

## TDD Approach

- **Unit tests** (added in S01, RED-first): in `tests/unit/test_auto_merge_classifier.py`:
  - `test_partial_allowlist_returns_partition` — two files in, one in allowlist; assert `eligible_files=(allowed,)`, `deferred_files=(blocked,)`, `skipped_reason is None`.
  - `test_all_deferred_keeps_skip_reason` — every file outside allowlist; assert `eligible_files=()`, `deferred_files==input`, `skipped_reason="not_allowlisted"`.
  - `test_refuselist_wins_over_partial_allowlist` — mix of refuse-list, allowlist, deferred; assert refuse-list short-circuits before partition runs.
  - `test_deferred_files_default_empty` — `ClassificationResult` constructor without `deferred_files` keyword still works (default = empty tuple).
- **Integration tests for event-metadata threading** (added in S02, RED-first, in `tests/integration/test_auto_merge_phase1.py` — these touch `_emit_event`/`db.commit()` so a real testcontainer DB is mandatory):
  - `test_attempt_resolution_attempted_event_includes_deferred_files`
  - `test_attempt_resolution_resolved_event_includes_deferred_files`
  - `test_attempt_resolution_failed_event_includes_deferred_files`
  - `test_attempt_resolution_default_deferred_files_empty`
- **Integration tests for end-to-end shape** (added in S03):
  - `test_auto_merge_partial_allowlist.py::test_cr00084_shape_partitions_event_metadata` — synthesize a worktree with the exact CR-00084 conflict shape; assert event metadata.
- **Updated tests**: Existing classifier tests that assert `eligible_files=()` in the partial case must be updated to assert the new partition. The existing `EVENT_AUTO_RESOLUTION_SKIPPED` integration test in `tests/integration/test_auto_merge_phase1.py` is tightened (S02) to also assert `event_metadata["deferred_files"]` matches the input. Other existing integration tests in `tests/integration/test_auto_merge_phase1.py` that pass an all-allowlisted conflict are unchanged.
- **TDD RED-evidence**: S01 and S02 must run the new failing tests before changing production code and record the RED output verbatim in their reports' `tdd_red_evidence` field. S03's RED evidence is the cumulative S01+S02 RED chain (the end-to-end integration test is the GREEN confirmation).

## Notes

- The follow-up Phase-2 promotion CR will reuse `deferred_files` to construct the operator's "still needs manual resolution" list when LLM proposals are applied to the worktree.
- `worktree_commit.sh` does not need a change for this CR — the bash script's "Rebase conflicts detected" message still lists every conflicted file (correct), and Python decides per-file whether the LLM is invoked. A future UX-polish CR could rewrite the bash error to consume the partition, but it is not necessary for the value this CR delivers.
- `executor/auto_merge.toml` requires no edit; only a comment update is acceptable if the implementer wants to document the new semantics in-place.
- The dashboard auto-merge view (`dashboard/routers/auto_merge_*.py`) will continue to render fine; the new metadata keys are additive. A follow-up UI CR can surface `deferred_files` as a distinct column if operators ask for it.
