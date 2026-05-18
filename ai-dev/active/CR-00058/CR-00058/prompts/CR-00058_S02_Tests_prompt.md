# CR-00058_S02_Tests_prompt

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S02
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network mutating command. Allowed: `docker ps`, `docker inspect`, `docker logs`, `./ai-core.sh`, `make`. Testcontainer fixtures spun up by pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step does not modify migrations. The integration fixture uses the standard testcontainer pattern from `tests/conftest.py`.

## Input Files

- `ai-dev/active/CR-00058/CR-00058_CR_Design.md` — design doc; AC1–AC5
- `orch/daemon/batch_manager.py` — current behavior of `_process_batch` (post-S01)
- `orch/daemon/scope_overlap.py` — post-S01 contract
- `orch/daemon/project_registry.py` — post-S01 contract
- `tests/conftest.py` — testcontainer + FTS DDL fixtures
- `tests/integration/test_f_00076_scope_extraction_round_trip.py` — pattern reference for F-00076 integration tests
- `tests/integration/test_batch_manager.py` — pattern reference for batch_manager integration tests
- `skills/iw-ai-core-testing/SKILL.md` (and `tests/CLAUDE.md`) — testing rules: real testcontainer DB, no mocks, FTS DDL after `create_all()`, psycopg URL fix
- `CLAUDE.md`, `orch/CLAUDE.md`
- Runtime step state via `uv run iw item-status CR-00058 --json`

## Output Files

- `ai-dev/active/CR-00058/reports/CR-00058_S02_Tests_report.md`
- New: `tests/integration/daemon/test_overlap_gate_policy.py`

## Context

S01 added unit coverage for the matching logic and config parsing. This step writes the end-to-end integration test that proves the daemon's `_process_batch` honors the policy across batches and emits the right DaemonEvents — the same shape as the real CR-00057 vs I-00087/I-00088 scenario.

Test conventions for this project (mandatory):

- Use the `db_session` (or equivalent) testcontainer fixture from `tests/conftest.py`. NEVER connect to the live DB.
- After `Base.metadata.create_all()` in any per-test schema setup, also execute `FTS_FUNCTION_SQL` and `FTS_TRIGGER_SQL` from `orch/db/models`.
- If you build a DB URL by hand, replace `postgresql+psycopg2://` with `postgresql+psycopg://` (psycopg v3).
- No mocking the DB. The whole point is to exercise the cross-batch query path.

## Requirements

### 1. Create `tests/integration/daemon/test_overlap_gate_policy.py`

Cover these scenarios in one focused test module:

#### `test_default_policy_holds_source_overlap_across_batches`

- Seed two projects in `projects` (or use the standard fixture project + an additional one if the fixture supports it).
- For the test project, do NOT set `overlap_gate` — exercise the synthesized default.
- Insert two batches in `executing` state under the test project.
- Insert in-flight `BatchItem(status=executing)` for work item A in Batch1 with `WorkItem.impacted_paths=["dashboard/foo.py"]`.
- Insert pending `BatchItem(status=pending)` for work item B in Batch2 with `WorkItem.impacted_paths=["dashboard/foo.py"]`.
- Build a real `BatchOrchestrator` (mirror the construction in `tests/integration/test_batch_manager.py`). Run one `_process_batch` cycle for Batch2.
- Assert: B's `BatchItem.status` remains `pending`; one `DaemonEvent` row with `event_type=item_held_for_scope` referencing B and the conflicting glob; **zero** `item_overlap_allowed_by_policy` events.

#### `test_permissive_allow_releases_overlap_and_emits_audit_event`

- Same shape as above, but set `Project.config["overlap_gate"] = {"block_on_overlap": ["**/*"], "allow_on_overlap": ["dashboard/**", "tests/**", "test/**", "__tests__/**", "**/*conftest*", "**/*.test.*", "**/*.spec.*"]}` for the test project.
- A's path: `dashboard/foo.py`, B's path: `dashboard/foo.py`.
- Reload the registry so the new project config is in memory.
- Run `_process_batch` for Batch2.
- Assert: B transitions to `setting_up` or `executing` (whatever `_launch_item` puts it into); exactly one `DaemonEvent` with `event_type=item_overlap_allowed_by_policy` and metadata containing `candidate_item_id=B`, `in_flight_item_ids=[A]`, `dropped_globs` includes `dashboard/foo.py`, `matched_allow_patterns` includes `dashboard/**`; zero `item_held_for_scope` events for B.

#### `test_per_conflicting_glob_precedence`

- A's paths: `["dashboard/x.py", "orch/foo.py"]`
- B's paths: `["dashboard/y.py", "orch/foo.py"]`
- `overlap_gate.allow_on_overlap = ["dashboard/**"]`
- Run `_process_batch`. Assert B is still **held** (because `orch/foo.py` is not allowlisted); the `item_held_for_scope` event metadata's `conflicting_globs` lists `orch/foo.py` only (NOT `dashboard/y.py`).

#### `test_dependency_graph_not_affected_by_policy`

- Two items in the same batch, A in `execution_group=0`, B in `execution_group=1`, A still `executing` (not merged).
- B has `WorkItem.impacted_paths=["docs/foo.md"]`; `overlap_gate.allow_on_overlap = ["**/*"]` (everything allowed).
- Run `_process_batch`. Assert B remains `pending` (held by execution_group, not by overlap). This proves the policy does NOT short-circuit dependency ordering.

### 2. Use the directory `tests/integration/daemon/`

If the directory does not exist, create it with an `__init__.py`. Look at sibling files (`test_batch_manager_worktree_hooks.py` lives in `tests/unit/daemon/`; integration daemon tests are typically under `tests/integration/daemon/` already — confirm path by listing the directory before writing the file).

### 3. Run only the new file before reporting

```bash
uv run pytest tests/integration/daemon/test_overlap_gate_policy.py -v
```

Do NOT run `make test-integration` — that's S13's job.

## Project Conventions

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` carefully — they encode the testcontainer + assertion rules. Notably:

- Assert against DB state via SELECTs, not just function return values.
- Pin `DaemonEvent.event_type` strings exactly — they're an audit-trail contract.
- Prefer one focused scenario per test over multi-purpose tests; readability beats LOC.

## TDD Requirement

For integration tests added in this step, RED is observed by running each test before its dependency (S01 implementation) is fully wired. Since S01 lands before S02, you should still write the test, run it, and confirm the failure is *behavioural* (assertion failure, missing event row) rather than `ImportError` / `AttributeError`. If S01's interfaces require small adjustments to make these tests pass cleanly, raise a blocker — do NOT silently patch S01 code from this step.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`:

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Run only `tests/integration/daemon/test_overlap_gate_policy.py`.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "tests-impl",
  "work_item": "CR-00058",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/daemon/test_overlap_gate_policy.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "4 passed, 0 failed",
  "tdd_red_evidence": "n/a — coverage-only step; cases written against S01-shipped contracts and exercise DB state directly",
  "blockers": [],
  "notes": ""
}
```
