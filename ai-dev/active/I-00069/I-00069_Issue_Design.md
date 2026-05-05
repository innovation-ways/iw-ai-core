# I-00069: Downgrade LiveDbConnectionRefusedError to DEBUG/WARNING in test context

**Type**: Issue
**Severity**: Low
**Created**: 2026-05-05
**Reported By**: I-00067 self-assessment (finding [5])
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

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

This incident does not modify migrations. Skip the migration policy
in practice — but the policy still applies.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

Every dashboard test run currently emits a noisy ERROR-level log line plus a
full Python traceback for `LiveDbConnectionRefusedError` during
`create_app()` startup. The refusal itself is the *intended, correct* behaviour
of `orch/db/live_db_guard.py` under `IW_CORE_TEST_CONTEXT=true` — but
`dashboard/app.py:146-149` swallows it via `logger.exception(...)`, which
emits at `ERROR` with traceback. Real errors are harder to spot in test
output as a result.

## Project Context

Read the project's [`CLAUDE.md`](../../../CLAUDE.md) for architecture,
conventions, and hard rules. Relevant per-package guides:

- [`dashboard/CLAUDE.md`](../../../dashboard/CLAUDE.md) — FastAPI factory, middleware patterns
- [`orch/CLAUDE.md`](../../../orch/CLAUDE.md) — `live_db_guard` is the connection chokepoint
- [`tests/CLAUDE.md`](../../../tests/CLAUDE.md) — `_arm_live_db_guard` fixture and pytest contract

## Steps to Reproduce

1. Run any dashboard-test that imports `dashboard.app.create_app`, e.g.:
   ```bash
   IW_CORE_TEST_CONTEXT=true uv run pytest tests/dashboard/test_alembic_guard_banner.py -q
   ```
2. Observe the captured stderr / log output for the test session.
3. Look for the line `alembic guard check failed at startup; continuing`
   followed by a traceback containing `LiveDbConnectionRefusedError`.

**Expected**: `LiveDbConnectionRefusedError` raised under `IW_CORE_TEST_CONTEXT=true`
is the guard doing its job. It should be logged at DEBUG (or at most WARNING,
without a traceback) and should not look like a failure to a reader scanning
test output.

**Actual**: It is logged at ERROR with a full traceback via
`logger.exception(...)` — visually indistinguishable from genuine startup
failures.

## Root Cause Analysis

`dashboard/app.py:142-150` performs a one-shot alembic-guard probe at app
construction:

```python
# Initial alembic guard check at app construction (R3).
# Suppress failures: if the DB is unreachable at boot, the middleware
# will retry on each request (with the same suppress) and the banner
# stays hidden. Mirrors the middleware's contextlib.suppress pattern.
try:
    app.state.alembic_guard_status = check_db_at_head()
except Exception:  # noqa: BLE001
    logger.exception("alembic guard check failed at startup; continuing")
    app.state.alembic_guard_status = None
```

`check_db_at_head()` opens an engine pointed at the live orch DB
(`IW_CORE_DB_HOST:IW_CORE_DB_PORT`, normally `localhost:5433`). When pytest
collection arms the test guard (`tests/conftest.py:_arm_live_db_guard`
sets `IW_CORE_TEST_CONTEXT=true`), `safe_create_engine` immediately raises
`LiveDbConnectionRefusedError` from `orch/db/live_db_guard.py:134-141` — the
guard's whole purpose is to **prevent** test code from touching the live DB.

The `except Exception` branch then routes that *expected, intentional*
refusal through `logger.exception(...)`, which logs at ERROR with a full
traceback. The middleware path
(`dashboard/middlewares/alembic_guard.py:54-58`) already does this correctly
via `contextlib.suppress(Exception)` — only the startup probe is loud.

For comparison, the daemon path (`orch/daemon/main.py:147`) uses
`logger.critical("alembic guard check failed: %s", exc)` without a
traceback — which is appropriate in daemon context where the live DB *is*
the target. Test context is the inverse: the refusal is success.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/app.py:146-149` | Logs expected `LiveDbConnectionRefusedError` at ERROR with traceback |
| Test output noise | Every dashboard test run shows a scary-looking ERROR + stack trace |
| Engineering ergonomics | Real test failures are harder to spot in CI logs |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend (`backend-impl`) | Update `dashboard/app.py` to catch `LiveDbConnectionRefusedError` separately and log at DEBUG when `IW_CORE_TEST_CONTEXT=true`, else WARNING (no traceback) | — |
| S02 | CodeReview (`code-review-impl`) | Review S01: scope, log levels, no behavioural change to `app.state.alembic_guard_status`, no other exception classes accidentally swallowed | — |
| S03 | Tests (`tests-impl`) | Add `tests/dashboard/test_live_db_guard_log_level.py`: reproduction + regression (semantic correctness) | — |
| S04 | CodeReview (`code-review-impl`) | Review S03: tests fail without S01, pass with S01, assert specific log levels and absence of traceback marker | — |
| S05 | CodeReview_Final (`code-review-final-impl`) | Global review across S01 + S03 | — |
| S06..S12 | QV Gates | lint, format, typecheck, arch-check, security-sast, unit-tests, integration-tests | — |
| S13 | self-assess-impl | Soft self-assessment (project flagged `self_assess = true`) | — |

No `qv-browser` step — backend-only, no UI surface affected.
No frontend gates — this project has no `frontend/` directory.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**: `dashboard/app.py`
- **Files to add**: `tests/dashboard/test_live_db_guard_log_level.py`
- **Nature of change**: Narrow the `except Exception` catch in
  `dashboard/app.py:146-149` to handle `LiveDbConnectionRefusedError`
  specifically. Log it at DEBUG when `IW_CORE_TEST_CONTEXT=true`, else
  WARNING (single-line message, no traceback). Keep the existing
  `logger.exception(...)` ERROR path for any other exception class so
  genuine boot failures still surface loudly.

## File Manifest

All files for this work item live under `ai-dev/active/I-00069/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00069_Issue_Design.md` | Design | This document |
| `I-00069_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00069_S01_Backend_prompt.md` | Prompt | S01 — backend fix |
| `prompts/I-00069_S02_CodeReview_Backend_prompt.md` | Prompt | S02 — review S01 |
| `prompts/I-00069_S03_Tests_prompt.md` | Prompt | S03 — reproduction + regression tests |
| `prompts/I-00069_S04_CodeReview_Tests_prompt.md` | Prompt | S04 — review S03 |
| `prompts/I-00069_S05_CodeReview_Final_prompt.md` | Prompt | S05 — global review |
| `prompts/I-00069_S13_SelfAssess_prompt.md` | Prompt | S13 — self-assessment (soft) |

QV gate steps (S06–S12) are script-driven — no prompt files needed.

Reports are created during execution in `ai-dev/active/I-00069/reports/`.

## Test to Reproduce

```python
# tests/dashboard/test_live_db_guard_log_level.py
import logging
import pytest
from dashboard.app import create_app


def test_i00069_live_db_guard_refusal_is_not_error_in_test_context(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RED before fix, GREEN after.

    Under IW_CORE_TEST_CONTEXT=true, dashboard startup MUST NOT log the
    expected LiveDbConnectionRefusedError at ERROR with a traceback.
    """
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    caplog.set_level(logging.DEBUG, logger="dashboard.app")

    create_app()  # raises nothing; the refusal must be swallowed

    error_records = [
        r for r in caplog.records
        if r.levelno >= logging.ERROR
        and "LiveDbConnectionRefused" in (r.getMessage() + (r.exc_text or ""))
    ]
    assert error_records == [], (
        "LiveDbConnectionRefusedError must NOT log at ERROR in test context; "
        f"got {len(error_records)} ERROR record(s)"
    )
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given IW_CORE_TEST_CONTEXT=true and a dashboard test imports create_app()
When the alembic-guard startup probe runs and raises LiveDbConnectionRefusedError
Then no ERROR-level log record is emitted, no traceback is logged,
     and the expected refusal is logged at DEBUG (single-line message)
```

### AC2: Regression test exists

```
Given the fix is applied
When pytest runs tests/dashboard/test_live_db_guard_log_level.py
Then the reproduction test passes (no ERROR records),
     and the regression test asserts a non-refused exception still surfaces at ERROR
```

### AC3: Behaviour is preserved

```
Given the fix is applied
When create_app() runs (test context or not)
Then app.state.alembic_guard_status is set exactly as before
     (None on any failure, or the GuardStatus on success)
```

## Regression Prevention

- The reproduction test asserts **specific** log levels (`>= ERROR`) for
  `LiveDbConnectionRefusedError`, not just "no logs" — preventing a future
  regression where a different exception path re-introduces the noise.
- A second test in the same file asserts a non-refused exception
  (`RuntimeError("synthetic")`) STILL logs at ERROR with traceback —
  preventing over-correction that silences genuine failures.
- The test scopes `caplog.set_level` to the `dashboard.app` logger to avoid
  interference from other loggers and avoid silencing global ERROR records.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/app.py`
- `tests/dashboard/test_live_db_guard_log_level.py`

## TDD Approach

- **Reproducing test**: `test_i00069_live_db_guard_refusal_is_not_error_in_test_context`
  — fails on `main` (records contain ERROR-level `LiveDbConnectionRefusedError`),
  passes after the fix.
- **Regression test**: `test_i00069_non_refusal_exception_still_logs_error`
  — monkey-patches `check_db_at_head` to raise `RuntimeError("synthetic")`
  and asserts the existing `logger.exception(...)` path still fires at
  ERROR. Prevents over-correction.
- **Unit tests**: covered by the two tests above (no new orch-layer logic).
- **Integration tests**: none required — change is dashboard-only.

## Notes

- The guard module itself (`orch/db/live_db_guard.py`) is **not** modified.
  Its ERROR-level `RuntimeError` subclass is correct context-free behaviour;
  only the dashboard's swallow of an *expected* exception is wrong.
- The middleware path
  (`dashboard/middlewares/alembic_guard.py:54-58`) already uses
  `contextlib.suppress(Exception)` and is silent — no change there.
- The daemon path (`orch/daemon/main.py:147`) is unaffected: the daemon
  legitimately targets the live DB, so a guard failure there is genuinely
  exceptional.
- Effort: S (~5–8 lines in `dashboard/app.py`, ~30 lines of tests).
