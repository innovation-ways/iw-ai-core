# I-00042: PostgreSQL `batch_item_status` enum missing `migration_invalid` and `migration_rolled_back` labels

**Type**: Issue
**Severity**: Medium
**Created**: 2026-04-26
**Reported By**: Operator (sergio) — observed in daemon logs after CR-00022 merge
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state
(`docker kill | stop | rm | restart | compose up/down/restart | volume rm | system prune`).

Allowed exceptions: testcontainers spun up by pytest fixtures, read-only introspection
(`docker ps | inspect | logs`), and invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orchestration DB
(port 5433) from an agent context. Your job in S01 is to WRITE the migration FILE — the
daemon will dry-run it against a testcontainer at merge time and apply it post-merge.

Allowed for agents: `alembic revision --autogenerate -m "..."` (writes a file only),
`alembic history | current | show` (read-only), and migrations executed inside
testcontainer fixtures.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Description

The Python `BatchItemStatus` enum in `orch/db/models.py` declares 13 values, but the
PostgreSQL `batch_item_status` enum on the live orchestration DB only has 11 — missing
`migration_invalid` and `migration_rolled_back`. The daemon's worktree re-attach query
binds the full Python enum value list and PostgreSQL rejects the unknown labels with
`InvalidTextRepresentation`. The daemon logs `Worktree re-attach failed — continuing`
on every restart and the re-attach loop is silently skipped, leaving any in-flight
batch items orphaned across daemon restarts.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Most
relevantly:

- `orch/db/migrations/versions/40af3b76e1d5_cr_00021_rebase_pipeline_phase.py` is the
  canonical pattern for adding labels to the `batch_item_status` enum: it uses
  `op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'X'")` and runs in
  autocommit mode (PostgreSQL forbids `ALTER TYPE … ADD VALUE` inside the same
  transaction as a use-site reference, so each ADD VALUE must commit before the
  enum label can be referenced).
- `orch/db/models.py:139-160` is the `BatchItemStatus` enum source of truth.
- The daemon merge pipeline in `orch/daemon/merge_queue.py` and
  `orch/daemon/migration_pipeline.py` writes `BatchItemStatus.migration_invalid` and
  `BatchItemStatus.migration_rolled_back` into the `batch_items.status` column on
  Phase 1 dry-run failure / Phase 3 rollback. These code paths exist today but
  would fail with `InvalidTextRepresentation` if ever exercised on the current PG enum.
- Current alembic head: `c062b6bf5eb3` (CR-00022 OSS redesign). The new migration
  must chain off it.

## Steps to Reproduce

1. Restart the daemon (`./ai-core.sh daemon restart`).
2. Tail `logs/daemon.log` immediately after startup.
3. Observe entries of the form:
   ```
   ERROR    orch.daemon.main: Worktree re-attach failed — continuing
   psycopg.errors.InvalidTextRepresentation: invalid input value for enum batch_item_status: "migration_invalid"
   ```
4. Run the live-DB introspection query:
   ```sql
   SELECT enumlabel FROM pg_enum
   WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname='batch_item_status')
   ORDER BY enumsortorder;
   ```
   Returns 11 labels — `pending`, `setting_up`, `executing`, `completed`, `merging`,
   `merged`, `failed`, `stalled`, `skipped`, `migration_rebase_failed`, `setup_failed`.
5. Compare to the Python enum:
   ```python
   from orch.db.models import BatchItemStatus
   [e.value for e in BatchItemStatus]
   ```
   Returns 13 values — additionally `migration_invalid` and `migration_rolled_back`.

**Expected**: Every `BatchItemStatus` value in the Python enum has a corresponding
label in the PG `batch_item_status` enum. Daemon worktree re-attach query binds
without error.

**Actual**: PG enum is missing `migration_invalid` and `migration_rolled_back`. Any
query that binds those Python enum values raises `InvalidTextRepresentation`.

## Root Cause Analysis

CR-00017 (daemon-only migration application) added `migration_invalid` and
`migration_rolled_back` to the Python `BatchItemStatus` enum
(`orch/db/models.py:151-152`) along with the migration_pipeline branches that write
those statuses (`orch/daemon/migration_pipeline.py`). However, no Alembic migration
was authored to extend the corresponding PostgreSQL enum.

CR-00021 later added `migration_rebase_failed` to both Python and PG enums (via
`40af3b76e1d5_cr_00021_rebase_pipeline_phase.py`), but did not retroactively add the
two CR-00017 labels. The drift has been latent ever since, surfacing as a daemon
log error on every startup once a query bound those values.

## Affected Components

| Component | Impact |
|-----------|--------|
| PG `batch_item_status` enum | Missing 2 labels → write/read of those values fails |
| `orch/daemon/main.py` `_reattach_worktrees` | Query crashes on every daemon startup; re-attach loop skipped |
| `orch/daemon/merge_queue.py` (`migration_invalid` write path) | Untriggered today, but would crash on Phase 1 dry-run failure |
| `orch/daemon/migration_pipeline.py` (`migration_rolled_back` write path) | Untriggered today, but would crash on Phase 3 rollback path |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Database | Add Alembic migration that ADDs both labels to `batch_item_status` (autocommit, IF NOT EXISTS, off head `c062b6bf5eb3`) | — |
| S02 | CodeReview | Review S01 migration | — |
| S03 | Tests | Reproduction test (PG enum has all 13 labels) + drift-prevention regression test that asserts the Python `BatchItemStatus` set ⊆ live PG enum labels | — |
| S04 | CodeReview | Review S03 tests for semantic correctness | — |
| S05 | CodeReview_Final | Global review across S01 + S03 | — |
| S06 | QV gate | lint | — |
| S07 | QV gate | format | — |
| S08 | QV gate | typecheck | — |
| S09 | QV gate | unit-tests | — |
| S10 | QV gate | integration-tests | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None (only the `batch_item_status` enum type is altered)
- **Migration notes**: Each `ALTER TYPE … ADD VALUE` must run **outside** a transaction
  (autocommit). Mirror the pattern in
  `orch/db/migrations/versions/40af3b76e1d5_cr_00021_rebase_pipeline_phase.py`. Use
  `IF NOT EXISTS` so the migration is idempotent. Down-revision: `c062b6bf5eb3`.
  The `downgrade()` cannot drop enum values in PG without rebuilding the type — leave
  the labels in place on downgrade and document this (same approach as `40af3b76e1d5`).

### Code Changes

- **Files to modify**: None — this is a pure schema fix.
- **Files to create**: One new migration file at
  `orch/db/migrations/versions/<rev>_i_00042_add_batch_item_status_labels.py`.

## File Manifest

All files for this work item live under `ai-dev/active/I-00042/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00042_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00042_S01_Database_prompt.md` | Prompt | S01 migration instructions |
| `prompts/I-00042_S02_CodeReview_Database_prompt.md` | Prompt | S02 review of migration |
| `prompts/I-00042_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00042_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of tests |
| `prompts/I-00042_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |

Source files modified:

| File | Type | Purpose |
|------|------|---------|
| `orch/db/migrations/versions/<rev>_i_00042_add_batch_item_status_labels.py` | New migration | Adds both enum labels |
| `tests/integration/test_batch_item_status_enum_drift.py` | New test | Reproduction + drift-prevention |

## Test to Reproduce

The reproduction test should fail before the fix is applied and pass after.

```python
# tests/integration/test_batch_item_status_enum_drift.py

from sqlalchemy import text
from orch.db.models import BatchItemStatus


def test_pg_batch_item_status_enum_matches_python(db_engine):
    """RED before I-00042: PG enum is missing migration_invalid and migration_rolled_back.
    GREEN after the migration runs in the testcontainer.
    """
    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT enumlabel FROM pg_enum "
                "WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname='batch_item_status') "
                "ORDER BY enumsortorder"
            )
        ).fetchall()
    pg_labels = {r[0] for r in rows}
    py_labels = {e.value for e in BatchItemStatus}

    # Semantic checks — assert the specific values, not just count
    assert "migration_invalid" in pg_labels
    assert "migration_rolled_back" in pg_labels
    # Drift prevention: every Python value must be present in PG
    missing = py_labels - pg_labels
    assert not missing, f"Python BatchItemStatus values missing from PG enum: {sorted(missing)}"
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given the I-00042 migration has been applied to the live orchestration DB
When I query pg_enum for batch_item_status
Then the result includes both 'migration_invalid' and 'migration_rolled_back'
And it includes every other value declared in the Python BatchItemStatus enum
```

### AC2: Regression test exists

```
Given the fix is applied
When the integration test suite runs against a fresh testcontainer
Then test_pg_batch_item_status_enum_matches_python passes
And the test would fail if a future Python BatchItemStatus value is added without a corresponding ALTER TYPE migration
```

### AC3: Daemon startup is clean

```
Given the migration has been applied
When the daemon is restarted
Then logs/daemon.log contains no "Worktree re-attach failed" entries with InvalidTextRepresentation
```

## Regression Prevention

The drift-prevention test in `tests/integration/test_batch_item_status_enum_drift.py`
asserts `{e.value for e in BatchItemStatus} ⊆ live_pg_enum_labels`. Any future addition to
the Python enum without a matching `ALTER TYPE … ADD VALUE` migration will fail this
test in CI.

For other enums in the schema (`work_item_status`, `step_status`, `phase`, etc.),
consider a follow-up CR to factor the same drift check into a parametrised test that
loops over every PG enum used by the ORM. Out of scope for this incident.

## Dependencies

- **Depends on**: None (chains off current head `c062b6bf5eb3`).
- **Blocks**: None.

## TDD Approach

- **Reproducing test**: `test_pg_batch_item_status_enum_matches_python` — fails on
  pre-migration testcontainer state, passes after the new migration runs.
- **Unit tests**: None needed — the bug is a pure schema fix.
- **Integration tests**: Reproduction test above. The testcontainer fixture in
  `tests/integration/conftest.py` already runs `alembic upgrade head` so the new
  migration will be applied automatically.

## Notes

- PostgreSQL forbids dropping enum labels without rebuilding the type. The
  `downgrade()` will leave the labels in place — same compromise CR-00021 made.
- The `ALTER TYPE … ADD VALUE` statements must run in autocommit mode (each on its
  own connection or with `op.get_bind().execution_options(isolation_level="AUTOCOMMIT")`).
  See the prior-art migration for the exact pattern.
