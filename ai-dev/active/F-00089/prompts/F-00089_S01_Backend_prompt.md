# F-00089_S01_Backend_prompt

**Work Item**: F-00089 -- Daemon chaos / fault-injection test layer
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived infrastructure containers are outside your scope. Touching them can cause multi-hour outages and data loss (see the 2026-04-22 incident in `docs/IW_AI_Core_DB_Setup.md`).

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures (they self-label and self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic against the live orchestration DB (port 5433). Your job is test-only. This step adds **no migrations**. Allowed: alembic inside testcontainer fixtures, `alembic history/current/show`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00089 --json` (canonical).
- `ai-dev/work/F-00089/F-00089_Feature_Design.md` — Design document (read in full).
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — testing standards.
- `docs/IW_AI_Core_Daemon_Design.md` — daemon design + state transitions.
- `orch/daemon/` — every module under here, read before designing the harness.
- `orch/config.py:222` — `IW_CORE_STALL_THRESHOLD` reader.

## Output Files

- `ai-dev/work/F-00089/reports/F-00089_S01_Backend_report.md` — Step report.

## Context

You are implementing **S01: Fault-injection harness** — the foundation that the five scenario steps (S02..S06) all build on. The harness API is the gate. If its shape is wrong, every scenario inherits the bug. **This is the most important step in this Feature.** You have a 3600s timeout — use it to iterate on the API before committing.

This is **test-only scope**. You must NOT modify any production code under `orch/daemon/`, `orch/`, `dashboard/`, `executor/`, or anywhere else. The daemon is exercised AS-IS through monkey-patch / dependency-injection hooks.

Read the design doc first (full Scope, Acceptance Criteria, Boundary Behavior, Invariants, TDD sections) before writing any code.

## Requirements

### 1. Create the chaos test package

Create the new package directory `tests/integration/daemon_chaos/` with at minimum:

- `__init__.py` (empty marker)
- `harness.py` — the harness implementation
- `conftest.py` — pytest fixtures (the `chaos_daemon` fixture, plus any shared sub-fixtures the scenarios need)

The package must be self-contained. Do NOT modify `tests/integration/conftest.py` — the chaos package brings its own conftest. The new conftest may import from `tests/integration/conftest.py` (it is a parent), but must not change it.

### 2. Implement the `chaos_daemon` fixture

The fixture must:

- Depend on the project's standard testcontainer Postgres fixture (so it inherits the isolated DB).
- Instantiate enough of the daemon's poll-loop machinery (from `orch/daemon/main.py` and related modules) to call **one or more poll cycles synchronously** under test control. Do NOT spawn a background thread or process — tests must drive the loop step-by-step via a method like `chaos_daemon.advance_one_cycle()`.
- Expose the five named injection hooks as methods on the fixture object (see requirement 3).
- Track which hooks are armed, and on teardown restore all monkey-patches and reset all module-level state (so tests can run back-to-back in the same pytest session without pollution).
- Refuse to start (raise a clear error at fixture-setup time) if the testcontainer Postgres fixture is not present — must NEVER silently connect to the live DB on port 5433.

### 3. Implement the five named injection hooks

All five must be deterministic. **No `os.kill`, no `subprocess.Popen.kill`, no `kill -9`, no `random.*`, no `time.sleep` longer than 5 seconds, no non-deterministic time source.** All injection is via monkey-patch or dependency injection.

The hook names (exposed as methods on the `chaos_daemon` fixture object):

1. `inject_worktree_setup_failure_after_clone()` — next worktree setup performed by the daemon passes `git worktree add` but fails the dependency-install step (e.g. `uv sync`). Configurable via an optional `stage=` argument so tests can also exercise "fail before git worktree add" (boundary-behavior row).
2. `inject_fix_cycle_always_fails()` — the CodeReview step's verdict is forced to `fail` with `mandatory_fix_count=1` on every fix cycle.
3. `inject_agent_stall_after_seconds(seconds: int)` — the next agent step's `last_heartbeat` is fast-forwarded so it appears to have stalled. Test fixtures should also override `IW_CORE_STALL_THRESHOLD` to a small value to bound wall-clock cost.
4. `inject_squash_merge_conflict_on_main()` — writes a conflicting commit to the testcontainer's simulated `main` branch immediately before the daemon attempts squash-merge for the mid-flight item.
5. `inject_migration_rebase_conflict_revision()` — writes a throwaway alembic revision file inside the worktree whose `down_revision` does not match the testcontainer DB's current head, so `orch/daemon/migration_rebase.py` fails.

Each hook must be **idempotent** (calling it twice before teardown does not double-patch / does not error). Each hook must record (on the fixture object) that it was triggered so tests can assert "yes the daemon hit this code path", not just "yes the work item ended in state X".

### 4. Document the harness contract

Add a module-level docstring at the top of `harness.py` that documents:

- What the harness is and is not (it is not a chaos-monkey; it is a deterministic injection layer).
- The full list of hook names + their signatures.
- The fixture lifecycle (setup, teardown, cleanup guarantees).
- The "never live DB" guard.
- A two-line code example of typical usage in a scenario test.

This docstring is the source of truth that S07's skill update (`skills/iw-ai-core-testing/SKILL.md`) will cross-link.

### 5. Determinism meta-test

Create `tests/integration/daemon_chaos/test_harness_is_deterministic.py` with at minimum one test that:

- Arms `inject_fix_cycle_always_fails()`.
- Advances the daemon through enough cycles to hit the fix-cycle cap.
- Records `WorkItem.fix_cycle_count`.
- Resets the fixture (calls teardown + re-setup) and repeats N=10 times.
- Asserts the same `fix_cycle_count` value every time (deterministic).

This is the canary that catches accidental non-determinism in later scenario steps.

### 6. Follow project conventions

Read `CLAUDE.md`, `tests/CLAUDE.md`, and `skills/iw-ai-core-testing/SKILL.md`. Key rules:

- NEVER connect tests to live DB (port 5433).
- MUST replace `postgresql+psycopg2://` URLs with `postgresql+psycopg://`.
- MUST run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in tests (if you spin up additional test DBs — though the standard fixture handles this).
- `DaemonEvent.metadata` is named `event_metadata` in Python.
- Strong assertions: no `assert True`, no `pytest.raises(Exception)` without `match=`, no mock-only tests. Every assertion has a target.

## TDD Requirement

Follow Red-Green-Refactor:

1. **RED**: Write the determinism meta-test (req 5) FIRST. Run it with a targeted invocation (`uv run pytest tests/integration/daemon_chaos/test_harness_is_deterministic.py -v`) and confirm it fails for the **right reason** — `AttributeError`/`NotImplementedError`/missing fixture, NOT `ImportError`/`SyntaxError`/collection error. Capture the failing line.
2. **GREEN**: Implement the harness + fixture + hooks until the meta-test passes.
3. **REFACTOR**: Clean up the harness API surface; ensure the module docstring is precise; remove any debug code.

Do not skip RED. Record the captured RED failure line in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift. Re-stage if it changes anything.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Populate the `preflight` object in the result contract. If a tool is unavailable, STOP and raise a blocker.

## Test Verification (NON-NEGOTIABLE)

Run **only the test files you wrote** in this step:

```bash
uv run pytest tests/integration/daemon_chaos/ -v
```

Do NOT run `make test-integration` or `make test-unit` — those are QV gates (S15/S16) with their own budgets. Do NOT report `tests_passed: true` unless your targeted tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "F-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/daemon_chaos/__init__.py",
    "tests/integration/daemon_chaos/harness.py",
    "tests/integration/daemon_chaos/conftest.py",
    "tests/integration/daemon_chaos/test_harness_is_deterministic.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/integration/daemon_chaos/test_harness_is_deterministic.py::test_harness_is_deterministic — AttributeError: 'NoneType' object has no attribute 'inject_fix_cycle_always_fails'  // captured RED run before implementing the fixture",
  "blockers": [],
  "notes": "Document any harness-API decisions that S02..S06 should know about."
}
```

- `tdd_red_evidence` is **required** — Backend step adding behavioural tests.
