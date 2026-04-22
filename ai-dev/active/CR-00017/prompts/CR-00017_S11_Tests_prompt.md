# CR-00017_S11_Tests_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S11
**Agent**: tests-impl

---

## ⛔ Docker is off-limits (EXCEPT testcontainers via pytest)
## ⛔ Migrations: agents generate, daemon applies

You're allowed to use testcontainers in pytest. You are NOT allowed to run
`alembic upgrade head` against the live DB from any test. All migration
tests must target testcontainer DBs.

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md` — Design (TDD Approach, AC1–AC10)
- S01/S03/S05/S07 reports
- `tests/conftest.py`, `tests/CLAUDE.md`
- Modules under test: `orch/db/safe_migrate.py`, `orch/daemon/migration_pipeline.py`, `orch/daemon/merge_queue.py`, `orch/daemon/batch_manager.py`, `orch/cli/migrations_commands.py`, `orch/cli/merge_queue_commands.py`
- From CR-00016: `tests/integration/test_agent_constraints_coverage.py` — extend this

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S11_Tests_report.md`
- `tests/unit/test_safe_migrate_guards.py` (new — focused guard/exit-path coverage beyond S03's smoke)
- `tests/integration/test_migration_pipeline.py` (new — 3-phase pipeline E2E)
- `tests/integration/test_migration_pipeline_frozen.py` (new — frozen-queue scenarios)
- `tests/integration/test_agent_migrate_guard.py` (new — agent-env guard integration)
- `tests/integration/test_agent_constraints_coverage.py` (MODIFY — add R2 marker check)
- Possibly: new fixtures in `tests/conftest.py`

## Context

Full test matrix for the 3-phase pipeline. Happy path, every failure path, frozen-queue behavior, multi-head detection, CLI exit codes, agent-env guard propagation through daemon subprocess spawning.

## Requirements

### 1. Unit tests — `tests/unit/test_safe_migrate_guards.py`

Beyond S03's smoke:

- Permutation matrix for agent-context guard: each of `apply`, `rollback` × `IW_CORE_AGENT_CONTEXT` in `{"true", "TRUE", "True", "1", "", unset, "false"}`. Only exact string `"true"` triggers the guard. (Document this semantic choice explicitly; it avoids footguns from values like "yes" or "1".)
- `dry_run` with `tempdb_url == live_db_url` raises `ValueError`.
- `list_pending_revisions` when DB is empty (fresh testcontainer, no alembic_version table) returns all revisions in order.
- `MultipleHeadsError.args` includes both heads.
- `pending_migration_log` is written even when the alembic call raises (check `phase='apply', success=False`).

### 2. Integration tests — `tests/integration/test_migration_pipeline.py`

Each test spins a fresh testcontainer DB (NOT the live DB), simulates a batch with a migration file, and exercises the daemon pipeline module directly (no need to run the full daemon loop).

- `test_pipeline_happy_path` — valid migration → Phase 1 pass → Phase 2 pass → batch state advances → `pending_migration_log` has 2 rows.
- `test_dry_run_rejects_broken_migration` — migration whose `upgrade()` raises → Phase 1 fails → batch marked `MIGRATION_INVALID` → NO squash-merge → `pending_migration_log` has 1 row.
- `test_apply_fails_rollback_succeeds` — migration passes dry-run but fails apply (simulate by mocking `safe_migrate.apply` to raise after dry-run success) → Phase 3 downgrades cleanly → batch marked `MIGRATION_ROLLED_BACK` → live DB back at previous revision.
- `test_apply_fails_rollback_fails_freezes_queue` — both apply AND rollback fail → `is_merge_queue_frozen()` returns True → next merge cycle skips all batches.
- `test_multi_head_state_rejected` — set up two heads in alembic script_dir → `run_pre_merge_dry_run` → `MultipleHeadsError` bubbled → batch marked `MIGRATION_INVALID`.

### 3. Integration tests — `tests/integration/test_migration_pipeline_frozen.py`

- `test_frozen_queue_blocks_merges` — set `merge_queue_frozen=true`, run a merge cycle, assert no batches merge.
- `test_unfreeze_resumes` — `iw merge-queue unfreeze --ack "test"` → `is_merge_queue_frozen()` returns False → next merge cycle processes batches.
- `test_unfreeze_refuses_in_agent_context` — set `IW_CORE_AGENT_CONTEXT=true`, invoke `iw merge-queue unfreeze --ack "..."`, assert exit 2, assert flag unchanged.
- `test_unfreeze_logs_ack_reason` — after unfreeze, `daemon_events` has a row with the ack reason and `acknowledged_by`.

### 4. Integration test — `tests/integration/test_agent_migrate_guard.py`

- `test_agent_env_propagates_to_subprocess` — invoke the daemon's agent-spawning code path (`batch_manager.py`'s spawn function) with a test stub that echoes `$IW_CORE_AGENT_CONTEXT`. Assert the value is `"true"` in the subprocess.
- `test_agent_cannot_apply_migration` — run `uv run iw migrations apply --i-am-operator` via subprocess with `IW_CORE_AGENT_CONTEXT=true` in env, assert exit 2, assert stdout names the guard.

### 5. Extend coverage test

In `tests/integration/test_agent_constraints_coverage.py`:

- Add a constant `MARKER_R2 = "⛔ Migrations: agents generate, daemon applies"`.
- New test `test_prompt_template_contains_migrations_rule` — parametrized over `PROMPT_TEMPLATES`, asserts `MARKER_R2 in template.read_text()`.
- Extend `test_policy_doc_exists_and_includes_rule` to assert both R1 (original marker) AND R2 markers present.
- Add `test_claude_md_references_migrations_policy` — asserts each CLAUDE.md mentions `alembic` AND `IW_AI_Core_Agent_Constraints` (any R1 OR R2 link satisfies the latter — they point at the same doc).

### 6. Testcontainer hygiene

- Every testcontainer has Ryuk labels (testcontainers library default — verify).
- Cleanup in fixture teardown.
- psycopg v3 URL replacement.
- FTS triggers after `create_all()`.
- No shared state between tests (each test has its own testcontainer).

### 7. Pytest markers

- All integration tests: `@pytest.mark.integration`.
- Long-running tests (pipeline E2E) tagged with `@pytest.mark.slow` if such a marker exists in this project.

### 8. Fixture hygiene

- If adding a shared fixture (e.g. `daemon_pipeline_env`), put it in `tests/conftest.py`.
- Use `monkeypatch.setenv` / `delenv` — NEVER `importlib.reload(orch.config)` (project rule).

## Project Conventions

- Tests in `tests/unit/` or `tests/integration/` per scope.
- Subprocess invocation: `subprocess.run` with `capture_output=True, text=True`.
- Mock `safe_migrate` / `migration_pipeline` calls where integration scope doesn't require the real thing (keeps tests fast).

## TDD Verification

Tests must fail on pre-CR-00017 code (modules don't exist, markers don't exist, guard behavior absent). Document this in the S11 report.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all pass.
2. `make test-integration` — all pass.
3. `make lint` — pass.
4. Tests run cleanly twice in a row (no leaked testcontainers, no leaked env vars).

## Subagent Result Contract

Standard JSON. `test_summary` should enumerate counts per file.

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S11
uv run iw step-done CR-00017 --step S11 --report ai-dev/active/CR-00017/reports/CR-00017_S11_Tests_report.md
```
