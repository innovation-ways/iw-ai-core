# F-00089_S06_Backend_prompt

**Work Item**: F-00089 -- Daemon chaos / fault-injection test layer
**Step**: S06
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step adds **no real migration**. Scenario 5 simulates a migration-rebase failure by writing a **throwaway** alembic revision file inside the testcontainer's per-worktree migration dir. The throwaway file MUST NOT be committed to the repo and MUST NOT touch the production orchestration DB at port 5433. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status F-00089 --json` — runtime step state.
- `ai-dev/work/F-00089/F-00089_Feature_Design.md` — Design document (AC6, Invariant 8, Boundary Behavior "Migration-rebase failure when no alembic revision exists").
- `ai-dev/work/F-00089/reports/F-00089_S01_Backend_report.md` — Harness API (`inject_migration_rebase_conflict_revision()`).
- `tests/integration/daemon_chaos/harness.py` + `conftest.py`.
- `orch/daemon/migration_rebase.py` — the rebase entrypoint (CR-00021).
- `orch/daemon/migration_pipeline.py` — broader migration pipeline.
- I-00075 / I-00076 — the revision-skew failure mode this scenario pins.

## Output Files

- `ai-dev/work/F-00089/reports/F-00089_S06_Backend_report.md` — Step report.

## Context

You are implementing **S06: Scenario 5 — migration-rebase failure**. The harness writes a throwaway alembic revision file whose `down_revision` does not match the testcontainer DB's current head, so `orch/daemon/migration_rebase.py` fails the pre-merge rebase step. Your tests assert the failure is detected, the item is marked, no migration is applied to the (testcontainer's) prod-mirror DB, and the worktree is preserved for inspection.

**Test-only scope.** Do NOT modify production code anywhere. 1800s timeout (alembic round-trip).

## Requirements

### 1. Create `tests/integration/daemon_chaos/test_migration_rebase_failure.py`

Tests required:

- `test_migration_rebase_failure_is_detected` — arm injection; advance daemon's migration-rebase pass; assert the failure is caught and logged with a traceback (assert against a DaemonEvent or the captured caplog output for the specific error class).
- `test_item_marked_migration_rebase_failed` — assert WorkItem.status is `migration_rebase_failed` (or whichever exact status name the daemon sets — check `orch.db.models.WorkItemStatus` for the actual enum value).
- `test_alembic_version_unchanged_after_failed_rebase` — capture `alembic_version.version_num` before the rebase attempt; advance daemon; capture again; assert they are identical (the failed rebase did not advance the DB head).
- `test_worktree_directory_preserved_for_inspection` — assert the worktree directory still exists on disk after the failed rebase (operator-inspection requirement). Optionally assert a marker file like `migration_rebase_failed.flag` is present if the daemon writes one.
- `test_no_alembic_revision_skips_scenario` — boundary-behavior row: worktree carries no new revision file. Test must `pytest.skip` with a clear reason (no rebase to fail). Do not assert.

### 2. Throwaway revision file hygiene

The injection hook from S01 (`inject_migration_rebase_conflict_revision()`) writes the throwaway revision file inside the testcontainer's isolated worktree — **never inside the host repo's `orch/db/migrations/versions/` directory**. Verify this in your test setup: assert the file is written to the testcontainer's filesystem, not the host repo (check the path doesn't match `{repo_root}/orch/db/migrations/versions/**`).

### 3. Assertion strength

Every test must assert against a daemon-mutated DB row, a daemon-emitted event row, or a verified filesystem state. No assertion-only-against-injection-hook tests.

### 4. Determinism

No wall-clock dependencies. Alembic operations inside the testcontainer are deterministic.

### 5. Follow project conventions

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`. Note the project's hard rule: **NEVER** apply an uncommitted Alembic migration to the production orch DB (CLAUDE.md hard rules). Your test enforces a different invariant in the testcontainer context — the rebase **failure** path must leave the testcontainer DB unchanged.

## TDD Requirement

Red-Green-Refactor:

1. **RED**: Write `test_alembic_version_unchanged_after_failed_rebase` first (it's the strongest invariant). Run it. Confirm it fails for the right reason — `AssertionError` from a version-num mismatch when the injection isn't armed correctly (or the daemon happens to advance the head despite the rebase error). Capture the failing line.
2. **GREEN**: Arm injection correctly.
3. **REFACTOR**: Add remaining tests.

Record the captured RED failure line in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — all must pass.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/daemon_chaos/test_migration_rebase_failure.py -v
```

Only this file. If you uncover a daemon bug, `xfail`-pin (`strict=True`), file an Incident, note in `notes`.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "Backend",
  "work_item": "F-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/daemon_chaos/test_migration_rebase_failure.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed (1 skipped)",
  "tdd_red_evidence": "tests/integration/daemon_chaos/test_migration_rebase_failure.py::test_alembic_version_unchanged_after_failed_rebase — AssertionError: <captured RED line>",
  "blockers": [],
  "notes": ""
}
```
