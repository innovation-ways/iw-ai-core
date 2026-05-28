# CR-00091: Alembic PENDING Sentinel — Make Migration Late-Binding Explicit

**Type**: Change Request
**Priority**: Medium
**Reason**: Eliminate the "stale green gate" problem where `make migration-check` validates a migration against head A but the migration merges against head C after drift
**Created**: 2026-05-28
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This CR modifies the tooling around migration file generation and the pre-merge rebase step. It does **not** add new migrations. The `migration_rebase.py` documentation update clarifies existing daemon behaviour — no DDL changes.

---

## Description

Agents currently bake a real Alembic revision ID into `down_revision` at worktree-creation time. If main advances before the item merges, `migration_rebase.py` silently fixes the value at merge time — but by then the `make migration-check` gate result is stale. This CR introduces a `"PENDING"` sentinel: agents always write `down_revision = "PENDING"` when generating a new migration; `migration_rebase.py` (which already handles this correctly) resolves it to the real head at merge time; and `make migration-check` resolves it dynamically before running the round-trip test.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key rules relevant to this CR: the `migration_rebase.py` pre-merge rebase runs inside `merge_queue._merge_item`'s serial critical section; `make migration-check` runs `tests/integration/test_migrations_round_trip.py` in a fresh testcontainer; agents must never apply migrations against the live DB on port 5433.

## Current Behavior

When a database-impl agent generates a migration, Alembic autogenerate sets `down_revision` to whatever the current chain head is at that moment (e.g., `"76250ecb2593"`). This value is committed verbatim. At QV time, `make migration-check` runs the round-trip test against that revision chain — which is correct at the moment of generation but becomes stale if main advances (new migrations land) while the worktree is still executing later steps. At merge time, `migration_rebase.py` detects the stale value and rewrites it, but the gate that validated the chain is now stale.

If the worktree stalls before reaching the merge queue (e.g., a pre-commit hook blocks a commit, as happened in CR-00086), `migration_rebase.py` never fires and the drift is invisible until a human notices.

## Desired Behavior

1. Agents generate migrations by running `make migration-pending MSG="…"` rather than `alembic revision --autogenerate` directly. This target: (a) runs autogenerate normally, (b) immediately rewrites the generated file's `down_revision` to the string literal `"PENDING"`, (c) prints a confirmation. The PENDING value is the canonical signal that the parent will be resolved at merge time.

2. `make migration-check` detects any `"PENDING"` values in the versions directory, resolves each one to the actual current chain head (by temporarily substituting in-place within a scratch copy), then runs the round-trip test against the resolved chain. The test result is therefore always valid against main's current head, not a stale snapshot.

3. `migration_rebase.py` requires no logic change — PENDING is already handled correctly by the existing rewrite condition (`PENDING ≠ any real revision ID → always rewrites`). A documentation comment and a unit test are added to make this invariant explicit and regression-proof.

4. `CLAUDE.md`, `orch/CLAUDE.md`, the three agent-creation skills (`iw-new-cr`, `iw-new-feature`, `iw-new-incident`), and the `Implementation_Prompt_Template.md` are updated to document the PENDING convention so agents across all future items adopt it automatically.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `scripts/rewrite_down_revision.py` | Does not exist | New script: rewrites `down_revision` to `"PENDING"` in a given migration file |
| `scripts/resolve_pending_migration.py` | Does not exist | New script: resolves all `"PENDING"` values in versions dir to actual chain head |
| `Makefile` `migration-pending` | Does not exist | New target: wraps autogenerate + calls rewrite script |
| `Makefile` `migration-check` | Runs pytest directly | Pre-resolves PENDING via script before running pytest |
| `orch/daemon/migration_rebase.py` | Handles PENDING implicitly | Add explicit documentation comment + invariant assertion |
| `tests/unit/daemon/test_migration_rebase.py` | No PENDING test case | Add test case for PENDING sentinel path |
| `tests/integration/test_migrations_round_trip.py` | Assumes real `down_revision` | Works with PENDING (resolved by pre-step) |
| `tests/unit/test_rewrite_down_revision.py` | Does not exist | New unit tests for the rewrite script |
| `CLAUDE.md` + `orch/CLAUDE.md` | No PENDING convention | Add rule: use `make migration-pending` |
| Skills + templates | No PENDING mention | Add PENDING convention to migration sections |

### Breaking Changes

- None for existing merged migrations (all have real `down_revision` values).
- Agents that call `alembic revision --autogenerate` directly instead of `make migration-pending` will continue to work — `migration_rebase.py` handles both. PENDING is the preferred convention, not an enforced constraint.

### Data Migration

- None. No schema changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | `scripts/rewrite_down_revision.py` + `migration-pending` Makefile target + unit tests | — |
| S02 | `backend-impl` | `scripts/resolve_pending_migration.py` + updated `migration-check` Makefile target + `migration_rebase.py` comment + unit/integration test updates | — |
| S03 | `code-review-impl` | Review S01 + S02 | — |
| S04 | `backend-impl` | Docs only: CLAUDE.md, orch/CLAUDE.md, skills, templates | — |
| S05 | `code-review-final-impl` | Global cross-step review | — |
| S06 | `qv-gate` | `make migration-check` | — |
| S07 | `qv-gate` | `make lint` | — |
| S08 | `qv-gate` | `make format-check` | — |
| S09 | `qv-gate` | `make type-check` | — |
| S10 | `qv-gate` | `make test-unit` | — |
| S11 | `qv-gate` | `make allure-integration` | — |
| S12 | `self-assess-impl` | Self-assessment | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: This CR does not add a migration. It changes how future migrations are generated.

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
| `CR-00091_CR_Design.md` | Design | This document |
| `CR-00091_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00091_S01_Backend_prompt.md` | Prompt | S01: rewrite script + migration-pending target |
| `prompts/CR-00091_S02_Backend_prompt.md` | Prompt | S02: resolver script + migration-check update + rebase docs |
| `prompts/CR-00091_S03_CodeReview_prompt.md` | Prompt | S03: review S01+S02 |
| `prompts/CR-00091_S04_Backend_prompt.md` | Prompt | S04: docs/skills/templates |
| `prompts/CR-00091_S05_CodeReview_Final_prompt.md` | Prompt | S05: final cross-step review |
| `prompts/CR-00091_S12_SelfAssess_prompt.md` | Prompt | S12: self-assessment |

## Acceptance Criteria

### AC1: New migration-pending target generates a PENDING migration

```
Given a developer runs: make migration-pending MSG="add_foo_column"
When the command completes
Then a new file exists in orch/db/migrations/versions/ with down_revision = "PENDING"
And the revision ID is a valid Alembic hex string
And the docstring and upgrade/downgrade bodies are intact
```

### AC2: migration-check resolves PENDING before validating

```
Given the versions directory contains a migration with down_revision = "PENDING"
When make migration-check is run
Then the round-trip test (upgrade head → schema parity → downgrade → upgrade) passes
And no PENDING value remains in the migration file after the test
```

### AC3: migration_rebase.py rewrites PENDING at merge time

```
Given a branch's migration file has down_revision = "PENDING"
And main has advanced since the branch was created
When run_pre_merge_rebase is called at merge time
Then the migration file's down_revision is rewritten to main's actual current head
And the RebaseResult has success=True and at least one Rewrite entry
```

### AC4: Existing migrations with real down_revision values are unaffected

```
Given the versions directory contains migrations with real hex down_revision values
When make migration-check is run
Then the round-trip test passes exactly as before (no resolver interference)
```

### AC5: rewrite_down_revision.py is idempotent

```
Given a migration file already has down_revision = "PENDING"
When scripts/rewrite_down_revision.py is called on that file
Then the file still has down_revision = "PENDING"
And no error is raised
```

### AC6: Convention is documented in CLAUDE.md and the three agent-creation skills

```
Given a new work item is created via iw-new-cr, iw-new-feature, or iw-new-incident
When the database-impl agent reads its prompt and the project CLAUDE.md
Then it finds an explicit instruction to use make migration-pending instead of alembic revision --autogenerate directly
```

## Rollback Plan

- **Database**: N/A — no schema changes.
- **Code**: Revert commit. `migration_rebase.py` is unchanged in logic; the new scripts are additive. Any migration file with PENDING that was generated under this CR can be manually re-resolved by running `scripts/resolve_pending_migration.py` or by editing the file directly.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: None
- **Blocks**: None (but improves all future database-impl steps)

## Impacted Paths

- `scripts/rewrite_down_revision.py`
- `scripts/resolve_pending_migration.py`
- `Makefile`
- `tests/unit/test_rewrite_down_revision.py`
- `tests/unit/daemon/test_migration_rebase.py`
- `tests/integration/test_migrations_round_trip.py`
- `orch/daemon/migration_rebase.py`
- `CLAUDE.md`
- `orch/CLAUDE.md`
- `ai-dev/templates/Implementation_Prompt_Template.md`
- `skills/iw-new-cr/SKILL.md`
- `skills/iw-new-feature/SKILL.md`
- `skills/iw-new-incident/SKILL.md`
- `.claude/skills/iw-new-cr/SKILL.md`
- `.claude/skills/iw-new-feature/SKILL.md`
- `.claude/skills/iw-new-incident/SKILL.md`

## TDD Approach

- **Unit tests** (`tests/unit/test_rewrite_down_revision.py`): rewrite a real hex down_revision, rewrite a None value, idempotency with existing PENDING, handles type-annotated form (`down_revision: str | None = "abc"`), raises cleanly when file has no `down_revision` line.
- **Unit tests** (`tests/unit/daemon/test_migration_rebase.py`): extend existing suite with a test case where the batch migration has `down_revision = "PENDING"` — assert that `run_pre_merge_rebase` produces a Rewrite entry resolving PENDING to main's head.
- **Integration tests** (`tests/integration/test_migrations_round_trip.py`): add a fixture that temporarily inserts a PENDING migration into the versions dir (pointing at a non-existent revision as a sentinel) and asserts that the `make migration-check` pre-resolver rewrites it before the testcontainer run.
- **Updated tests**: the existing round-trip test must continue to pass unchanged (AC4 regression guard).

## Notes

- `migration_rebase.py` handles PENDING correctly today because `"PENDING" != any_real_revision_id` always evaluates True, causing the rewrite branch to execute. The documentation comment makes this invariant visible so future refactors don't accidentally break it (e.g., by adding an early-exit for "no staleness detected").
- The resolver script (`resolve_pending_migration.py`) rewrites files in-place. In a worktree, this is safe because the worktree is ephemeral. In a developer's local checkout, running `make migration-check` with a PENDING file will permanently resolve it — which is the intended workflow (the developer then commits the resolved value).
- The `migration-pending` target requires a `MSG` argument (enforced via Makefile error). Usage: `make migration-pending MSG="add_foo_column"`.
- **Relationship between AC2 and AC3** (intentional, not a contradiction). `make migration-check` (AC2) resolves PENDING in-place during the QV phase, so by the time the agent commits its working tree the file already has a hex `down_revision`. `migration_rebase.py` (AC3) is therefore a *backstop* — it only rewrites when `main` has drifted further between the QV-gate run and the pre-merge phase (typically a small window, on the order of the QV sequence duration). This CR **does not eliminate** the stale-gate problem; it **shrinks** the staleness window from "entire workflow duration" (potentially hours) to "post-QV duration" (typically minutes). AC3's `PENDING`-at-merge-time precondition is a regression-prevention guarantee for the degenerate path (worktree stalled before QV, manual re-runs, future workflow changes that skip the resolver).
- **Multi-PENDING chains within one batch are out of scope.** If a future batch contains two work items that each generate a PENDING migration in the same worktree, the resolver resolves only the root PENDING file; any PENDING→PENDING link is left as-is. This is acceptable because batches presently add at most one migration per work item, but a multi-migration CR would need to extend the resolver to topologically sort PENDING entries before resolving.
