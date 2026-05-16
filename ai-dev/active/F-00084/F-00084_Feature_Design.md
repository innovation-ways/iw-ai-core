# F-00084: LLM-Assisted Merge Conflict Resolution — Phase 0 Plumbing + Phase 1 Dry-Run

**Type**: Feature
**Priority**: Medium
**Created**: 2026-05-16
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in `tests/integration/` are exempt.
The Phase 1 dry-run never touches docker; the LLM is invoked as a subprocess via the existing `executor/step_executor.sh` runtime in the worktree, identical to fix-cycle steps.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This feature adds NO migrations.** The four new `DaemonEvent` event types reuse the existing `event_type` TEXT column and the flexible `event_metadata` JSONB column — see `orch/db/models.py:1271` (`DaemonEvent`). Refuse-list explicitly bars `orch/db/migrations/versions/*` from any LLM resolution attempt — Phase 1 must NOT touch Alembic chain files even in dry-run.

## Description

Lay the plumbing for LLM-assisted merge conflict resolution and ship a Phase 1 dry-run mode that captures what an LLM would propose for every conflict, without ever applying it. The full design (decision tree, refuse-list, allowlist, prompt template, event schema, phased rollout, acceptance criteria) is specified in [R-00076 §5](../../../docs/research/R-00076-llm-automated-merge-resolution.md); this Feature implements **Phase 0 (plumbing) + Phase 1 (dry-run audit)** only. Phase 2 (tests-only auto-apply with verification gate) and Phase 3 (broader allowlist) are deferred to follow-up CRs after Phase 1 has collected two weeks of audit data.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key constraints relevant to this Feature:
- The daemon polls every 60s and is the only thing that should call into `executor/worktree_commit.sh` or invoke LLM agents.
- All operational state lives in PostgreSQL (port 5433) — no files, no race conditions.
- The merge queue (`orch/daemon/merge_queue.py`) already serialises all merges; this Feature does NOT add a new lock.
- Per-step agent + model selection lives in `agent_runtime_options` (F-00081); this Feature reuses that table — operators pick which CLI tool + model the resolver uses via `executor/auto_merge.toml`.

## Scope

### In Scope

- New file `executor/auto_merge.toml` — phase, allowlist, refuse-list, limits, runtime-option pointer. Default `phase = 0` (plumbing only).
- Edits to `executor/worktree_commit.sh` — classify each conflict file against refuse-list / allowlist, emit a new stdout marker `AUTO_RESOLVE_REQUESTED=<json>` when at least one conflict is allowlisted, add a `--resume-rebase` flag (no-op stub for Phase 1 — surface only).
- New module `orch/daemon/auto_merge.py` — TOML config loader, classifier (refuse / allowlist / structural-rule / unclassified), per-file LLM invocation via `step_executor.sh` (agent + model from `agent_runtime_options` looked up from config), prompt builder (template from R-00076 §5.5), event emitter for the four new event types.
- Edits to `orch/daemon/merge_queue.py` `_merge_item()` — detect `AUTO_RESOLVE_REQUESTED` marker, call `auto_merge.attempt_resolution()`, on dry-run mode (`phase = 1`) ALWAYS persist event + abort, never call `git rebase --continue`.
- Four new `DaemonEvent.event_type` strings (no enum widening needed — column is TEXT): `merge_auto_resolution_attempted`, `merge_auto_resolved`, `merge_auto_resolution_failed`, `merge_auto_resolution_skipped`.
- Fixture-based integration tests reproducing I-00085 and I-00086 conflict shapes; refuse-list safety test; operator-UX-unchanged test.
- Unit tests for config loader, classifier, prompt builder, marker parser.

### Out of Scope

- The verification gate (lint + type-check + targeted tests on the resolved worktree) — Phase 2 CR.
- Applying the LLM's resolution (`git add` of resolved files + `git rebase --continue`) — Phase 2 CR.
- Allowlist expansion beyond `tests/**`, `docs/**`, `ai-dev/active/**/reports/**` — Phase 3 CR.
- Dashboard UI to surface auto-resolution audit events — out of scope; events are queryable via existing `daemon_events` table and dashboard event view.
- Operator command `iw merge-queue inspect-attempt <ID>` — nice-to-have, out of scope for Phase 1.
- New schema columns on `daemon_events` — explicitly avoided; JSONB metadata is sufficient.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | pipeline-impl | `executor/worktree_commit.sh` edits + new `executor/auto_merge.toml` | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | backend-impl | New `orch/daemon/auto_merge.py` + edits to `orch/daemon/merge_queue.py` | After S02 |
| S04 | code-review-impl | Per-agent review of S03 | — |
| S05 | code-review-final-impl | Cross-agent review of S01..S04 | — |
| S06 | tests-impl | Fixture-based integration tests + unit tests | After S05 |
| S07 | code-review-impl | Per-agent review of S06 | — |
| S08 | code-review-final-impl | Final cross-agent review including tests | — |
| S09..S16 | qv-gate | lint, assertions, format-check, type-check, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S17 | self-assess-impl | `iw-item-analyze` post-mortem | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration required. New event types are TEXT values in `daemon_events.event_type`; `daemon_events.metadata` (Python: `event_metadata`) is JSONB and already accepts arbitrary payloads.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **browser_verification**: false

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `F-00084_Feature_Design.md` | Design | This document |
| `F-00084_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00084_S01_Pipeline_prompt.md` | Prompt | Bash + TOML edits |
| `prompts/F-00084_S02_CodeReview_Pipeline_prompt.md` | Prompt | Per-agent review of S01 |
| `prompts/F-00084_S03_Backend_prompt.md` | Prompt | `auto_merge.py` + `merge_queue.py` integration |
| `prompts/F-00084_S04_CodeReview_Backend_prompt.md` | Prompt | Per-agent review of S03 |
| `prompts/F-00084_S05_CodeReview_Final_prompt.md` | Prompt | Cross-agent review of S01..S04 |
| `prompts/F-00084_S06_Tests_prompt.md` | Prompt | Fixture-based AC tests + unit tests |
| `prompts/F-00084_S07_CodeReview_Tests_prompt.md` | Prompt | Per-agent review of S06 |
| `prompts/F-00084_S08_CodeReview_Final_prompt.md` | Prompt | Final cross-agent review including tests |
| `prompts/F-00084_S17_SelfAssess_prompt.md` | Prompt | Self-assessment via iw-item-analyze |

Reports are created during execution in `ai-dev/active/F-00084/reports/`.

## Acceptance Criteria

### AC1: I-00085 shape conflict triggers dry-run capture (anchored to R-00076 AC-1)

```
Given a fixture-built bare repo with main at the equivalent of pre-I-00085 main
  AND a branch with the equivalent of I-00085's db247e8a wip commit (touching
      the 3 runtime-option test files identically to I-00084's already-merged
      changes — comment drift over identical numeric updates)
  AND executor/auto_merge.toml configured with phase = 1, allowlist including
      tests/**, and refuse-list per R-00076 §5.2
When  the daemon invokes worktree_commit.sh on this branch
Then  worktree_commit.sh detects exactly 3 conflict files
  AND classifies all 3 as allowlisted (none refuse-listed)
  AND emits AUTO_RESOLVE_REQUESTED=<json with 3 file paths> on stdout
  AND merge_queue.py parses the marker
  AND auto_merge.attempt_resolution() is invoked
  AND a merge_auto_resolution_attempted DaemonEvent is recorded with
      conflict_files = [3 paths], phase = 1, policy_decision = "allowlist"
  AND 3 LLM calls are issued (one per file) using the cli_tool + model from
      the auto_merge.toml-configured runtime_option_id
  AND a merge_auto_resolved DaemonEvent is recorded WITH metadata containing
      the proposed resolved file contents for each file AND llm_calls metadata
      (model, prompt_hash, output_hash, input_tokens, output_tokens)
  AND the rebase is aborted (NOT continued — Phase 1 is dry-run)
  AND a merge_conflict DaemonEvent is recorded as today
  AND BatchItem.status = merge_failed (operator UX unchanged)
```

### AC2: I-00086 shape conflict triggers dry-run capture (anchored to R-00076 AC-2)

```
Given a fixture-built bare repo with main at the equivalent of pre-I-00086 main
  AND a branch with the equivalent of I-00086's b207b22d wip commit (where
      one conflict is the hardcoded-vs-dynamic assertion divergence and
      another is the _PREV_REVISION constant divergence)
  AND auto_merge.toml configured for phase = 1 dry-run
When  the daemon invokes worktree_commit.sh on this branch
Then  the 3 conflict files are detected and classified as allowlisted
  AND auto_merge.attempt_resolution() is invoked
  AND the LLM prompt for each file contains:
        - the merge-base content of that file
        - main's version (ours during rebase)
        - the branch's version (theirs during rebase)
        - the recent commit log on both sides
        - the work-item title and description
  AND merge_auto_resolved fires with the proposed resolutions in metadata
  AND the rebase is aborted
```

### AC3: Refuse-list never invokes LLM (anchored to R-00076 AC-3)

```
Given a fixture-built repo with a conflict in
      orch/db/migrations/versions/d1e2f3gpt53c_*.py (synthetic conflict —
      both sides edit the migration body)
  AND auto_merge.toml configured for phase = 1
When  the daemon invokes worktree_commit.sh on this branch
Then  worktree_commit.sh classifies the file as refuse-listed
  AND NO AUTO_RESOLVE_REQUESTED marker is emitted
  AND NO LLM call is made
  AND a merge_auto_resolution_skipped DaemonEvent fires with
      reason = "refuse_list" and conflict_files containing the migration path
  AND the rebase is aborted exactly as today
  AND merge_conflict DaemonEvent fires as today
```

### AC4: Operator UX unchanged on any failure path (anchored to R-00076 AC-5)

```
Given any conflict — refuse-listed, allowlisted but LLM aborted, or any
      transient failure during auto_merge.attempt_resolution()
When  the merge queue processes the item
Then  BatchItem.status transitions to merge_failed
  AND a merge_conflict DaemonEvent fires with the conflict file list
  AND `iw merge-queue retry-merge <ID>` resets the BatchItem to completed
      and clears the merge_info exactly as today
  AND no prior behaviour of operator commands or dashboard event view is
      changed
```

### AC5: Phase 0 (plumbing-only) is a fully-functional no-op

```
Given auto_merge.toml with phase = 0 (default)
When  any conflict occurs (refuse-listed or allowlisted)
Then  worktree_commit.sh STILL emits AUTO_RESOLVE_REQUESTED for allowlisted
      conflicts (decision tree runs)
  AND merge_queue.py STILL parses the marker
  AND auto_merge.attempt_resolution() short-circuits BEFORE any LLM call
  AND a merge_auto_resolution_skipped DaemonEvent fires with reason = "phase_0"
  AND no LLM tokens are consumed
  AND merge_conflict + merge_failed fire as today
```

### AC6: Configuration is hot-reloadable (no daemon restart needed)

```
Given the daemon is running with auto_merge.toml phase = 0
When  the operator edits auto_merge.toml to phase = 1 and SIGHUPs the daemon
Then  the next conflict triggers Phase 1 behaviour (LLM call + audit event)
  AND no daemon restart is required
  AND the change is recorded in a config_reloaded DaemonEvent (reuse existing
      project_registry SIGHUP path)
```

## Boundary Behavior

Every row becomes a mandatory test case in S06.

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| All conflict files refuse-listed | Single conflict in `orch/db/migrations/versions/x.py` | `merge_auto_resolution_skipped` with `reason=refuse_list`; no LLM call; abort |
| Some refuse-listed, some allowlisted | Mixed `tests/x.py` + `orch/db/migrations/versions/y.py` | `merge_auto_resolution_skipped` with `reason=mixed_refuse_list`; no LLM call; abort (refuse-list wins — defence in depth) |
| All allowlisted | 3× `tests/*.py` conflicts | `merge_auto_resolution_attempted` → 3× LLM calls → `merge_auto_resolved` (Phase 1) with proposed resolutions in metadata; abort |
| LLM returns literal `ABSTAIN` | One file's LLM output is exactly `ABSTAIN` | That file's `abstained = true`; whole attempt result `success = false`; `merge_auto_resolution_failed` with `failed_reason=abstain` |
| LLM subprocess exits non-zero | step_executor.sh returns 1 | `merge_auto_resolution_failed` with `failed_reason=llm_error` and stderr captured in metadata; existing merge_conflict still fires |
| Conflict hunk exceeds `max_conflict_hunk_lines` | Conflict region > 80 lines | `merge_auto_resolution_skipped` with `reason=hunk_too_large`; no LLM call |
| More than `max_conflicted_files_per_merge` files in conflict | 6 conflict files (limit = 5) | `merge_auto_resolution_skipped` with `reason=too_many_files`; no LLM call |
| Binary file in conflict | `.png` or `.zst` | `merge_auto_resolution_skipped` with `reason=binary`; no LLM call |
| Empty TOML / missing config | `executor/auto_merge.toml` absent | `auto_merge.toml` defaults loaded; `phase = 0`; behaviour identical to today |
| Malformed TOML | Syntax error in file | Daemon logs ERROR, falls back to phase=0; emits `auto_merge_config_invalid` event; merge continues with today's behaviour |
| `runtime_option_id` points to nonexistent row | Configured id has been deleted | Fallback to project's default `agent_runtime_options.is_default=True`; if no default, `merge_auto_resolution_failed` with `failed_reason=runtime_option_missing` |
| `AUTO_RESOLVE_REQUESTED` marker malformed | Bash emits broken JSON | merge_queue.py logs ERROR, treats as plain conflict, abort as today |
| Phase 1 with `--resume-rebase` flag invoked | (Should be unreachable in Phase 1) | `worktree_commit.sh` rejects with exit 2 and an error message ("resume-rebase not available in phase 1"); abort |

## Invariants

Each invariant maps to a test in S06.

1. **No LLM token is ever consumed for a refuse-listed file.** Tested by AC3 and by asserting `llm_calls == []` in the resulting event metadata.
2. **No LLM token is ever consumed when `phase = 0`.** Tested by AC5.
3. **Phase 1 NEVER calls `git add` on a resolved file and NEVER calls `git rebase --continue`.** Tested by snapshotting the worktree's git state before/after — index must be unchanged.
4. **Existing operator commands behave identically to today on the failure path.** Tested by AC4: `iw merge-queue retry-merge` must still work; `merge_conflict` event payload must be byte-identical to today's emission (modulo timestamps).
5. **`event_metadata` is bounded: no single event exceeds 256 KB.** Tested by injecting an 8-file conflict with each file content artificially padded — implementation must truncate or refuse before storage. Rationale: prevent JSONB row explosion that could degrade event-view queries.
6. **The decision tree is deterministic.** Same `(conflict_files, auto_merge.toml)` always produces the same classification. Tested by unit tests for `classify_conflict_file()`.
7. **The agent + model used for the LLM call is the one declared in `auto_merge.toml`'s `runtime_option_id`** (or project default if unset). Tested by inspecting `llm_calls.model` in event metadata against the configured row.
8. **A failed LLM call NEVER leaves the worktree in a half-resolved state.** Tested by asserting that on `merge_auto_resolution_failed`, `git status` in the worktree shows the same UU markers it had before the attempt, and `git rebase --abort` succeeds without prompt.

## Dependencies

- **Depends on**: F-00081 (per-step agent_runtime_options table — this Feature reuses it for the resolver's runtime selection); CR-00021 (pre-merge migration-rebase phase — refuse-list interacts with it); F-00076 (existing `CONFLICT_FILES` marker parsing in `merge_queue.py` — this Feature follows the same pattern).
- **Blocks**: Phase 2 CR (auto-apply with verification gate); Phase 3 CR (broader allowlist).

## Impacted Paths

- `executor/auto_merge.toml`
- `executor/worktree_commit.sh`
- `orch/daemon/auto_merge.py`
- `orch/daemon/merge_queue.py`
- `tests/integration/test_auto_merge_phase1.py`
- `tests/integration/test_auto_merge_refuse_list.py`
- `tests/unit/test_auto_merge_config.py`
- `tests/unit/test_auto_merge_classifier.py`
- `tests/unit/test_auto_merge_prompt.py`
- `tests/unit/test_auto_merge_marker.py`
- `tests/fixtures/auto_merge/**`

## TDD Approach

- **Unit tests**:
  - `test_auto_merge_config.py` — TOML parsing, defaults, malformed-file fallback, missing-file fallback.
  - `test_auto_merge_classifier.py` — every refuse-list pattern matches its intended files; every allowlist pattern matches its intended files; mixed refuse+allow conflict resolves to refuse; binary detection; hunk-size limit.
  - `test_auto_merge_prompt.py` — prompt builder emits the R-00076 §5.5 template structure; ABSTAIN escape clause present; full files (not hunks) embedded; no PII leakage (no env vars in prompt).
  - `test_auto_merge_marker.py` — `AUTO_RESOLVE_REQUESTED=<json>` parser: valid JSON, malformed JSON, missing marker, multiple markers.

- **Integration tests** (fixture-based, using existing testcontainer pattern):
  - `test_auto_merge_phase1.py` — AC1 (I-00085 shape), AC2 (I-00086 shape), AC4 (operator UX), AC5 (phase 0), AC6 (hot reload).
  - `test_auto_merge_refuse_list.py` — AC3 (migration refuse-list), all refuse-list patterns from auto_merge.toml.

- **Edge cases** (covered in Boundary Behavior table above):
  - Mixed refuse + allow → refuse wins
  - LLM ABSTAIN token
  - LLM subprocess error
  - Oversized conflict hunk
  - Too-many-files conflict
  - Binary file
  - Missing/malformed TOML
  - Malformed AUTO_RESOLVE_REQUESTED marker
  - Invalid runtime_option_id

- **Fixture pattern**: Each AC test creates a fresh `tmp_path` git repo with:
  1. `git init --bare main.git`
  2. Clone, seed with a commit creating the test files at "main-base" state
  3. Branch and add a commit modifying those files (the "theirs" side — simulating I-00085/I-00086)
  4. Switch to main, add another commit modifying same files differently (the "ours" side — simulating I-00084's merge)
  5. Run the merge_queue subprocess against this fixture-repo, asserting on emitted DaemonEvent rows

  This avoids any dependency on actual git history of this repo and gives reproducible AC-anchored tests.

## Notes

- **R-00076 is the canonical reference.** This design doc intentionally references R-00076 §5 by section number rather than duplicating the design content. The implementation prompts (S01, S03, S06) all link back to R-00076 sections; reviewers (S02, S04, S05, S07, S08) MUST cross-check implementation against R-00076 §5.
- **Risk: dry-run JSONB row size.** With a 3-file conflict where each file is ~5 KB, the `merge_auto_resolved` event metadata is ~15 KB. Invariant 5 caps single-event size at 256 KB; the test enforces truncation/rejection on oversized payloads. Phase 2 (Phase 1's audit data will tell us whether to keep inlining or move to a sidecar storage).
- **Risk: LLM hallucinating a non-allowlisted file.** Mitigated by the prompt's explicit "output only the resolved file content for `<exact_relative_path>`" and by S06's unit test asserting the prompt names the target file.
- **Risk: race between SIGHUP config reload and an in-flight merge.** The merge queue is serialised; the reload happens on poll boundaries (60s). Worst case: one merge runs with the old config — acceptable for dry-run.
- **Future Phase 2 surface already planted**: the `--resume-rebase` flag is a stub in this Feature so the daemon's call site can be wired in Phase 2 without re-touching `worktree_commit.sh`.
- **Self-assessment expected to flag the LLM-call invariance**: S17's self-assess should confirm that Phase 1 ran without any LLM-actually-resolved merges — that's the correct outcome. If self-assess shows any `merge_auto_resolved` event for this very item's worktree, that's a bug in dry-run gating.
