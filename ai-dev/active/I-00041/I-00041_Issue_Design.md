# I-00041: Connection-layer guard against integration tests writing to the live orchestration DB

**Type**: Issue
**Severity**: Critical
**Created**: 2026-04-26
**Reported By**: Operator (sergio) — observed live during CR-00022 execution
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers spun up by pytest fixtures, read-only
introspection (`docker ps`, `docker inspect`, `docker logs`), and
invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live
orchestration DB (port 5433) from an agent context. This issue ADDS NO
new migration — it only adds runtime/connection-layer guards.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Description

Integration tests can connect to and mutate the live orchestration DB on port
5433. The current "agent context" guard in `orch/db/safe_migrate.py` is the
only protection, it is opt-out, and `tests/conftest.py:23` autouse-deletes the
env var that arms it — so any pytest run starts with the guard disabled.
A second bug compounds it: `orch/db/safe_migrate.py:_write_migration_log` calls
`get_db_url()` directly, bypassing the mocks tests place on `safe_apply` /
`safe_rollback` at the migration_pipeline import boundary. Together, these
allow a stale or runaway test process to silently corrupt live operational
state.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.
Most relevantly:

- `orch/db/identity.py` is the canonical pattern for a "fail-fast at boot" DB
  precondition (CR-00014). The new connection-layer guard mirrors that style:
  one helper, one chokepoint, opt-in only.
- `orch/db/session.py` exports the `engine`, `SessionLocal`, and `get_session`
  context manager. Every legitimate orch-DB connection comes through here.
- `orch/db/safe_migrate.py` already builds engines directly via
  `create_engine(...)` in several helpers (`_acquire_migration_lock`,
  `_release_migration_lock`, `_write_migration_log`, `_current_revision_from_db`,
  and the alembic-config builders). All of these need to be routed through the
  same chokepoint.
- `tests/conftest.py:23` currently runs `monkeypatch.delenv("IW_CORE_AGENT_CONTEXT",
  raising=False)` autouse — this is the polarity inversion described below.
- `tests/integration/conftest.py` is the testcontainer fixture entry point and
  is the source of legitimate test DB URLs (random port, never 5433).
- `IW_CORE_EXPECTED_INSTANCE_ID` (CR-00014) is the canonical fingerprint of
  the live orch DB. We use it as the primary match, with host:port (5433) as
  fallback when no fingerprint is set.

## Steps to Reproduce

1. Have the live DB at any non-base alembic head with the F-00062 migration
   applied.
2. Have a worktree's `orch/db/migrations/versions/` directory contain a
   migration whose `upgrade()` would fail when applied to the live DB
   (e.g. CR-00022's `c062b6bf5eb3`).
3. From that worktree, run `uv run pytest tests/unit/ tests/integration/ -v`.
4. Observe rows accumulating in live `pending_migration_log` with
   `batch_id=42` (the value hardcoded in
   `tests/integration/test_migration_pipeline.py`).
5. Observe `alembic_version` walking back two steps past F-00062 within
   minutes.
6. Observe the dashboard returning HTTP 500 on every route that loads
   `BatchItem` (`dashboard/routers/worktrees.py:502` nav-badge most prominent).

**Expected**: The integration test suite connects only to a testcontainer
Postgres (random port, ephemeral). Any code path that resolves to the live
orch DB (port 5433, matching `IW_CORE_EXPECTED_INSTANCE_ID`) raises
immediately with a loud error.

**Actual**: Tests connect to 5433 transparently. The only existing guard is
opt-out, the test conftest opts out for the entire session, and at least one
helper bypasses the mocks tests rely on.

## Root Cause Analysis

The orch DB has no defense-in-depth against unauthorised writes. The single
existing guard, `_assert_not_agent_context()` in `orch/db/safe_migrate.py`,
fails for three reasons:

1. **Wrong layer.** It only guards `safe_apply` / `safe_rollback` /
   `safe_dry_run`. Other helpers in the same file (`_acquire_migration_lock`,
   `_write_migration_log`) and any future caller of `create_engine(get_db_url())`
   bypass it entirely.
2. **Wrong polarity.** It is opt-out (env var must be set to *enable* the
   guard). `tests/conftest.py:23` autouse-deletes the var, so every pytest
   run starts unguarded.
3. **Wrong fingerprint.** It checks an env var, not the actual DB target.
   A connection to 5433 with the env var unset proceeds happily.

The 152 rows we observed in `pending_migration_log` with `batch_id=42` come
from `tests/integration/test_migration_pipeline.py` (lines 29, 70, 95, 150,
190 — all `batch_id = 42`). The tests *do* mock `safe_apply` and `safe_rollback`
at `orch.daemon.migration_pipeline.{safe_apply,safe_rollback}`, but the inner
helper `_write_migration_log` calls the real `get_db_url()` (`safe_migrate.py:200`)
to open a fresh short-lived session — that path is not covered by the mocks
and writes straight to 5433.

The fix is a **connection-layer chokepoint**: every engine creation in `orch/`
goes through one helper that refuses to connect to the live orch DB unless an
explicit operator/daemon opt-in env var is set. Tests that target a
testcontainer URL (random port, distinct fingerprint) are unaffected.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/db/session.py` | Engine factory must enforce the new guard at every call site. Engine creation becomes lazy via module `__getattr__` so importing the module does not fire the guard (preserves backwards compat for agents that import the package without ever connecting). Exports new `safe_create_engine(url, **kwargs)` chokepoint. |
| `orch/db/safe_migrate.py` | Internal helpers (`_acquire_migration_lock` line 312, `_release_migration_lock` line 346, `_write_migration_log` line 200, `_current_revision_from_db` line 170, alembic config builders) currently `create_engine(...)` directly — must route through `safe_create_engine`. The opt-out `_assert_not_agent_context` becomes a thin wrapper that delegates to the new guard for backwards compatibility, then is deprecated. |
| `orch/daemon/main.py` | `create_session_factory` (line 64) currently calls raw `create_engine` — must route through `safe_create_engine` so the daemon's session factory inherits the chokepoint. |
| `orch/daemon/migration_pipeline.py` | Two raw `create_engine` calls (lines 231, 266) — must route through `safe_create_engine`. |
| `orch/daemon/migration_rebase.py` | Two raw `create_engine` calls (lines 210, 239) — must route through `safe_create_engine`. |
| `orch/daemon/worktree_compose.py` | One raw `create_engine` call (line 224) inside `_emit_event` — must route through `safe_create_engine`. |
| `orch/cli/merge_queue_commands.py` | One raw `create_engine` call (line 51) — must route through `safe_create_engine`. |
| `tests/conftest.py` | Replace the autouse `monkeypatch.delenv("IW_CORE_AGENT_CONTEXT")` (line 23) with a session-scoped fixture that *sets* `IW_CORE_TEST_CONTEXT=true` and unsets `IW_CORE_OPERATOR_APPLY` / `IW_CORE_DAEMON_CONTEXT`. |
| `orch/cli/migrations_commands.py` | The `iw migrations apply --i-am-operator` command sets `IW_CORE_OPERATOR_APPLY=true` inside `apply_migrations` (line 152), inside a try/finally so the env mutation is scoped to that one invocation. |
| `orch/daemon/__main__.py` | The daemon entry point (line 11+) sets `IW_CORE_DAEMON_CONTEXT=true` BEFORE constructing `Daemon(config)`. `main.py` defines no `def main()` / `__name__ == "__main__"` — the actual entry is `__main__.py`, and `Daemon.__init__` (line 142) calls `create_session_factory` immediately, so arming MUST happen before the constructor runs. |
| `orch/daemon/batch_manager.py`, `orch/daemon/fix_cycle.py`, `orch/daemon/doc_job_poller.py` | Every site that launches a subprocess running agent or QV-gate code MUST strip `IW_CORE_DAEMON_CONTEXT` and `IW_CORE_OPERATOR_APPLY` from the child env before adding `IW_CORE_AGENT_CONTEXT=true`. Without this, the daemon's own allow-list flag leaks into agent processes and re-opens the bug for the canonical attack path (QV `make test-unit` running under an agent subprocess). Centralised via a new helper `_agent_subprocess_env()` in `orch/daemon/batch_manager.py`. |
| `dashboard/` | **No code changes.** The dashboard runs under the daemon's environment when launched via `./ai-core.sh start` and inherits `IW_CORE_DAEMON_CONTEXT=true`. Standalone launch (rare) relies on the guard's "no flag set → allowed" default-allow path; hardening this is deferred to a follow-up incident. |
| `tests/integration/test_migration_pipeline.py` | Hardcoded `batch_id = 42` (5 places) replaced with a unique-per-test value derived from xdist worker id + test name. Mock coverage extended to every code path that reaches `_write_migration_log`. (Belt-and-braces — primary fix is the connection-layer guard.) |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | New `orch/db/live_db_guard.py` chokepoint + `safe_create_engine` wrapper in `orch/db/session.py`. Route every `create_engine(...)` call site in `orch/` through it: `orch/db/safe_migrate.py` (4 sites + alembic config), `orch/daemon/main.py` (`create_session_factory` line 64), `orch/daemon/migration_pipeline.py` (lines 231, 266), `orch/daemon/migration_rebase.py` (lines 210, 239), `orch/daemon/worktree_compose.py` (line 224), `orch/cli/merge_queue_commands.py` (line 51). Deprecate `_assert_not_agent_context` (delegate to new guard). | — |
| S02 | CodeReview_Backend | Review S01 | — |
| S03 | Backend | Invert `tests/conftest.py:23` polarity; arm `IW_CORE_DAEMON_CONTEXT` in `orch/daemon/__main__.py` BEFORE `Daemon(config)` construction; arm `IW_CORE_OPERATOR_APPLY` in `iw migrations apply` (try/finally scoped); add `_agent_subprocess_env()` helper that strips allow-list flags and apply at all 5 agent/gate launch sites in `orch/daemon/`. | — |
| S04 | CodeReview_Backend | Review S03 | — |
| S05 | Tests | Reproduction test (subprocess attempts live-DB connect → asserts refusal); regression tests across daemon/operator/test contexts; fix `tests/integration/test_migration_pipeline.py` hardcoded `batch_id` and bypassed mock paths. | — |
| S06 | CodeReview_Tests | Review S05 | — |
| S07 | CodeReview_Final | Global review across S01/S03/S05 | — |
| S08..S12 | QV Gates | lint / format / typecheck / unit-tests / integration-tests (project-canonical 5-gate set; matches I-00040 / CR-00022 / `Makefile` targets) | — |

No QV Browser step (backend-only — fix touches no UI code; the dashboard
symptom is downstream of the schema corruption and is verified by existing
dashboard browser tests).

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: This issue adds NO migration. Pure runtime guard.

### Code Changes

- **Files to create**:
  - `orch/db/live_db_guard.py`
  - `tests/unit/test_live_db_guard.py`
  - `tests/unit/test_agent_subprocess_env.py`
  - `tests/integration/test_live_db_guard_reproduction.py`
- **Files to modify (S01 — chokepoint wiring)**:
  - `orch/db/session.py` (export `safe_create_engine`; lazy `__getattr__` for `engine` / `SessionLocal`)
  - `orch/db/safe_migrate.py` (4 raw `create_engine` sites + `_build_alembic_config` defensive call)
  - `orch/daemon/main.py` (`create_session_factory` line 64)
  - `orch/daemon/migration_pipeline.py` (lines 231, 266)
  - `orch/daemon/migration_rebase.py` (lines 210, 239)
  - `orch/daemon/worktree_compose.py` (line 224)
  - `orch/cli/merge_queue_commands.py` (line 51)
- **Files to modify (S03 — env-var arming + executor strip)**:
  - `orch/daemon/__main__.py` (set `IW_CORE_DAEMON_CONTEXT=true` BEFORE `Daemon(config)` construction)
  - `orch/cli/migrations_commands.py` (try/finally-scoped `IW_CORE_OPERATOR_APPLY=true` in `apply_migrations` only)
  - `orch/daemon/batch_manager.py` (new `_agent_subprocess_env()` helper; apply at lines ~565 (`_run_gate_command`), ~776 (agent launch), and `_build_agent_env` ~1054)
  - `orch/daemon/fix_cycle.py` (apply helper at line ~733 fix-cycle subprocess)
  - `orch/daemon/doc_job_poller.py` (apply helper at line ~171 doc-job launch — currently uses bare `os.environ.copy()`)
  - `tests/conftest.py` (invert polarity at line 23)
  - `tests/integration/test_migration_pipeline.py` (unique `batch_id` per test, expanded mocks, helper extraction)
- **Nature of change**: Add one chokepoint helper for engine creation;
  route every existing engine-creation call in `orch/` through it; invert
  the test conftest polarity from opt-out to opt-in; centralise allow-list
  stripping for every agent/gate subprocess launch; replace hardcoded
  test fixtures.

## File Manifest

All files for this work item live under `ai-dev/active/I-00041/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00041_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00041_S01_Backend_prompt.md` | Prompt | Connection-layer guard implementation |
| `prompts/I-00041_S02_CodeReview_Backend_prompt.md` | Prompt | Review of S01 |
| `prompts/I-00041_S03_Backend_prompt.md` | Prompt | Conftest polarity inversion + opt-in env vars |
| `prompts/I-00041_S04_CodeReview_Backend_prompt.md` | Prompt | Review of S03 |
| `prompts/I-00041_S05_Tests_prompt.md` | Prompt | Reproduction + regression tests + offending-test cleanup |
| `prompts/I-00041_S06_CodeReview_Tests_prompt.md` | Prompt | Review of S05 |
| `prompts/I-00041_S07_CodeReview_Final_prompt.md` | Prompt | Global review |

Reports are created during execution in `ai-dev/active/I-00041/reports/`.

## Test to Reproduce

```python
# tests/integration/test_live_db_guard_reproduction.py
"""Reproduction test for I-00041.

Spawns a fresh subprocess with IW_CORE_TEST_CONTEXT=true (the post-fix
test default) and the live orch DB URL. Asserts the subprocess fails
with the expected guard error and exit code, and that no row was
written to pending_migration_log on the live DB.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_subprocess_under_test_context_cannot_connect_to_live_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduces I-00041: a test process must NOT be able to connect to 5433.

    Uses IW_CORE_DB_HOST / IW_CORE_DB_PORT from the operator's environment
    (the same vars production reads), not a separate IW_*_FOR_TEST var, so
    there is no "test-only" knob that could drift from production.
    """
    live_host = os.environ.get("IW_CORE_DB_HOST", "localhost")
    live_port = os.environ.get("IW_CORE_DB_PORT", "5433")
    live_url = f"postgresql://iw_orch:iw_orch@{live_host}:{live_port}/iw_orch"

    code = (
        "import os; os.environ['IW_CORE_TEST_CONTEXT']='true'; "
        "from orch.db.session import safe_create_engine; "
        f"e = safe_create_engine({live_url!r}); "
        "c = e.connect(); c.close()"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "IW_CORE_TEST_CONTEXT": "true"},
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Must fail loudly with a guard error, not silently succeed.
    assert result.returncode != 0, (
        f"GUARD FAILED — subprocess connected to live DB. stdout={result.stdout!r}"
    )
    assert "LiveDbConnectionRefused" in result.stderr, (
        f"GUARD FIRED but with the wrong message: {result.stderr!r}"
    )
    assert live_port in result.stderr, (
        f"Refusal message must include the offending port: {result.stderr!r}"
    )
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a pytest process with IW_CORE_TEST_CONTEXT=true (the post-fix default)
When code in that process calls create_engine(<live orch DB URL>)
Then a LiveDbConnectionRefused error is raised before the connection opens
And no row is written to any table on the live DB on port 5433
```

### AC2: Daemon and operator paths still work

```
Given the daemon process with IW_CORE_DAEMON_CONTEXT=true
When the daemon calls SessionLocal() or any safe_migrate helper
Then the connection succeeds normally

Given the iw migrations apply --i-am-operator command
When it sets IW_CORE_OPERATOR_APPLY=true and calls safe_apply
Then the migration applies normally

Given the iw migrations dry-run command (testcontainer URL, no opt-in flag set)
When it runs against a non-live URL
Then it succeeds (the guard short-circuits when is_live_db_url returns False)

Given the iw migrations list-pending command (live DB read, no opt-in flag set)
When the operator runs it from their shell
Then it succeeds (the guard's "no flag set → allowed" default-allow path
preserves backwards compatibility for ad-hoc operator commands)
```

### AC3: Reproduction test exists

```
Given the fix is applied
When tests/integration/test_live_db_guard_reproduction.py runs
Then it passes (the guard is verified to fire on a real live URL)
```

### AC4: Mock-bypass path is closed

```
Given tests/integration/test_migration_pipeline.py is run with the post-fix code
When any of its tests execute
Then no rows are written to pending_migration_log on the live DB
And every test uses a unique batch_id (no hardcoded 42)
```

## Regression Prevention

Four structural changes prevent recurrence:

1. **Single chokepoint**: every engine creation in `orch/` routes through
   `orch/db/live_db_guard.assert_engine_url_allowed()`. New code that does
   `create_engine(get_db_url())` automatically inherits the guard. There is
   no second, parallel path that can drift out of compliance.

2. **Opt-in polarity**: tests start with the strongest possible state
   (`IW_CORE_TEST_CONTEXT=true`, no opt-out env vars set). A future test
   author who tries to "delete an inconvenient env var" strips a *guard
   removal*, not a guard.

3. **Fingerprint-based match**: the guard primarily compares
   `IW_CORE_EXPECTED_INSTANCE_ID` against the connecting URL's instance
   fingerprint (read at connect time via the existing identity helpers).
   Port-based matching (5433) is a fallback for early-boot situations.
   This means swapping the live DB to a different port never weakens the
   guard.

4. **Allow-list strip at agent/gate subprocess launch**: every site in
   `orch/daemon/` that spawns agent code or QV-gate work routes through
   `_agent_subprocess_env()`, which pops `IW_CORE_DAEMON_CONTEXT` and
   `IW_CORE_OPERATOR_APPLY` before adding `IW_CORE_AGENT_CONTEXT=true`.
   This closes the canonical attack path the original incident took
   (daemon → agent → `make test-unit` → live DB write). Without this
   step, the daemon's own arming in (1) leaks via `os.environ`
   inheritance and the guard's allow-list lets the agent through.

## Dependencies

- **Depends on**: None (orthogonal to CR-00022, which is in flight)
- **Blocks**: None directly. Strongly recommended to merge before any
  future migration that adds a destructive `downgrade()` path, because
  the same class of bug would corrupt that migration's data too.

## TDD Approach

- **Reproducing test** (RED first): subprocess test verifying that a
  process with `IW_CORE_TEST_CONTEXT=true` cannot connect to the live DB
  URL. Fails before S01 lands; passes after.
- **Unit tests** (`tests/unit/test_live_db_guard.py`):
  - URL fingerprint matches live → refused.
  - URL with same host:port but different fingerprint → allowed (covers
    the testcontainer-on-5433 unlikely edge case).
  - Refusal message contains the URL host:port and the offending env
    context name (`test`/`agent`).
  - `IW_CORE_OPERATOR_APPLY=true` allows live URL through.
  - `IW_CORE_DAEMON_CONTEXT=true` allows live URL through.
  - `IW_CORE_TEST_CONTEXT=true` refuses live URL.
  - Both opt-in flags can coexist (e.g. operator running daemon code
    locally) without contradiction.
- **Integration tests** (`tests/integration/test_live_db_guard_reproduction.py`,
  plus extending existing `tests/integration/test_migration_pipeline.py`):
  - Subprocess reproduction (above).
  - `_write_migration_log` invocation under test context lands no row on
    live DB (run against testcontainer URL with deliberate fingerprint
    spoofing).
  - `iw migrations apply --i-am-operator` succeeds against testcontainer.
- **Existing-test cleanup**: replace hardcoded `batch_id = 42` (5 places)
  in `tests/integration/test_migration_pipeline.py` with a per-test fixture
  that yields a unique large negative integer (negatives never collide with
  real batch ids); extend mocks so every call path that reaches
  `_write_migration_log` is covered.

## Notes

- **Backwards compatibility**: `IW_CORE_AGENT_CONTEXT` is **deprecated**, not
  removed. The new guard is authoritative; the old check becomes a thin
  delegator that logs a `DeprecationWarning` and forwards to the new helper.
  This avoids breaking the daemon and dashboard if either has an in-flight
  branch that still relies on the old name. The shim should be removed in a
  follow-up incident once 30 days have passed without warnings firing.
- **Why two opt-in vars (`IW_CORE_DAEMON_CONTEXT` and `IW_CORE_OPERATOR_APPLY`)
  instead of one**: separation of concerns. The daemon process needs live-DB
  access for *all* its work; the `iw migrations apply` CLI needs it for
  *one* command's lifetime. Conflating them would let a future bug in any
  daemon code path silently apply migrations.
- **The 201 stale `phase='rebase'` rows in `pending_migration_log`** are left
  alone. They were written by the daemon's legitimate migration-rebase phase
  during the runaway window and the daemon still uses that phase value.
  Truncating them would be a data-loss action for tidiness only.
- **Operational state when this incident lands**: the runaway pytest from
  `.worktrees/I-00038/.venv/` (PID 344986) was killed manually 2026-04-26;
  F-00062's migration was reapplied; CR-00022 is in flight (S05 just
  completed). The fix in this incident is structural — once merged it
  prevents recurrence. No data restoration is required from this incident.
- **Severity rationale**: Critical because the failure mode is silent data
  corruption of operational tables (`alembic_version`, `pending_migration_log`,
  `batch_items`) that the daemon and dashboard depend on for correctness.
  The 4-hour dashboard outage today is the visible symptom; future
  recurrences could mutate `work_items` or `batch_items` rows directly,
  with no easy recovery path.
