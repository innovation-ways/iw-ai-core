# I-00062_S05_Tests_prompt

**Work Item**: I-00062 -- Agent subprocess inherits orch DB env vars, allowing migrations to leak to port 5433
**Step**: S05
**Agent**: Tests (`tests-impl`)

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Read-only
introspection allowed. Testcontainers spawned by pytest fixtures are
exempt — Ryuk-managed. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch
DB on port 5433. Testcontainer-based migration round-trip in your tests
is exactly how this should work — that's safe.

**Do NOT run bare `make`** — see I-00062's own root cause. `make
test-unit` and `make test-integration` are the test verification gates
and are safe.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00062/I-00062_Issue_Design.md` — design document, "Test to
  Reproduce", "TDD Approach", and "Acceptance Criteria" sections
- `ai-dev/active/I-00062/reports/I-00062_S03_Backend_report.md` — S03 backend
  report (for behavior reference)
- All files modified by S01 and S03:
  - `orch/db/models.py`
  - `orch/db/migrations/versions/<id>_i_00062_add_worktree_db_credentials.py`
  - `orch/daemon/worktree_compose.py`
  - `orch/daemon/batch_manager.py`
  - `orch/config.py`
- `tests/conftest.py` — testcontainer fixtures, env scrubbing patterns
- `tests/CLAUDE.md` — test conventions

## Output Files

- `ai-dev/active/I-00062/reports/I-00062_S05_Tests_report.md` — step report
- `tests/unit/daemon/test_agent_subprocess_env.py` — new
- `tests/integration/daemon/test_launch_step_env_isolation.py` — new
- `tests/unit/orch_config/test_agent_context_failfast.py` — new
- `tests/integration/db/test_i_00062_migration.py` — new

## Context

You are writing the regression test suite for I-00062. The fix has three
defense layers and one persistence change; you must test each
independently and a full integration test that exercises the
end-to-end `_launch_step` path.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Tests must verify **specific values**, not just response shape:

- BAD: `assert "IW_CORE_DB_PORT" in env` (key existence only — passes
  even if value is wrong)
- BAD: `assert env.get("IW_CORE_DB_PORT")` (truthiness only)
- GOOD: `assert env["IW_CORE_DB_PORT"] == "36216"` (semantic — exact
  expected value)
- GOOD: `assert "IW_CORE_DB_PORT" not in env` (semantic — explicit
  absence)
- GOOD: `assert env["IW_CORE_DB_HOST"] != "localhost-orch-host"`
  (semantic — value is NOT the leaked one)

Every assertion must verify the **specific** expected behavior, not just
that the dict has keys.

## Requirements

### 1. Unit tests for `_agent_subprocess_env` (`tests/unit/daemon/test_agent_subprocess_env.py`)

Pure-function tests for the snapshot+strip behaviour. No DB, no
testcontainer — `monkeypatch` only.

```python
"""Unit tests for I-00062 — _agent_subprocess_env snapshot + strip."""

from __future__ import annotations

import pytest

from orch.daemon.batch_manager import _agent_subprocess_env


class TestAgentSubprocessEnvDoesNotLeakOrchDB:
    """I-00062 reproduction: ensure orch DB connection vars do not leak
    from the daemon's env into the agent subprocess env."""

    def test_strips_inherited_orch_db_vars(self, monkeypatch):
        """Pre-fix: this test FAILS — os.environ.copy() leaks 5433.
        Post-fix: passes — _agent_subprocess_env strips IW_CORE_DB_*."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")
        monkeypatch.delenv("IW_CORE_ORCH_DB_PORT", raising=False)

        env = _agent_subprocess_env()

        assert "IW_CORE_DB_HOST" not in env
        assert "IW_CORE_DB_PORT" not in env
        assert "IW_CORE_DB_NAME" not in env
        assert "IW_CORE_DB_USER" not in env
        assert "IW_CORE_DB_PASSWORD" not in env

    def test_snapshots_orch_creds_before_strip(self, monkeypatch):
        """I-00062 Layer 1: BEFORE stripping IW_CORE_DB_*, snapshot the
        daemon's values into IW_CORE_ORCH_DB_* so the Layer 3 guard has
        a known orch reference. This is what makes the guard fire for
        legacy worktrees whose .env still mirrors main."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")
        monkeypatch.delenv("IW_CORE_ORCH_DB_HOST", raising=False)
        monkeypatch.delenv("IW_CORE_ORCH_DB_PORT", raising=False)
        monkeypatch.delenv("IW_CORE_ORCH_DB_NAME", raising=False)
        monkeypatch.delenv("IW_CORE_ORCH_DB_USER", raising=False)
        monkeypatch.delenv("IW_CORE_ORCH_DB_PASSWORD", raising=False)

        env = _agent_subprocess_env()

        assert env["IW_CORE_ORCH_DB_HOST"] == "localhost"
        assert env["IW_CORE_ORCH_DB_PORT"] == "5433"
        assert env["IW_CORE_ORCH_DB_NAME"] == "iw_orch"
        assert env["IW_CORE_ORCH_DB_USER"] == "iw_orch"
        assert env["IW_CORE_ORCH_DB_PASSWORD"] == "iw_orch_dev"

    def test_snapshot_does_not_overwrite_existing_orch_creds(self, monkeypatch):
        """If IW_CORE_ORCH_DB_* is already set (e.g. by browser_env),
        the snapshot must use setdefault and NOT clobber."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")
        monkeypatch.setenv("IW_CORE_ORCH_DB_HOST", "preset-host")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")

        env = _agent_subprocess_env()

        assert env["IW_CORE_ORCH_DB_HOST"] == "preset-host"
        assert env["IW_CORE_ORCH_DB_PORT"] == "5433"

    def test_orch_db_url_vars_not_stripped(self, monkeypatch):
        """IW_CORE_ORCH_DB_* is the legitimate operator path for
        iw step-done / step-fail / step-start. Must NOT be stripped."""
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_ORCH_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_ORCH_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_ORCH_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PASSWORD", "iw_orch_dev")

        env = _agent_subprocess_env()

        assert env["IW_CORE_ORCH_DB_HOST"] == "localhost"
        assert env["IW_CORE_ORCH_DB_PORT"] == "5433"
        assert env["IW_CORE_ORCH_DB_NAME"] == "iw_orch"
        assert env["IW_CORE_ORCH_DB_USER"] == "iw_orch"
        assert env["IW_CORE_ORCH_DB_PASSWORD"] == "iw_orch_dev"

    def test_agent_context_flag_armed(self, monkeypatch):
        """IW_CORE_AGENT_CONTEXT=true must be set after the strip."""
        env = _agent_subprocess_env()
        assert env["IW_CORE_AGENT_CONTEXT"] == "true"

    def test_extra_overrides_strip(self, monkeypatch):
        """Browser-verification path injects IW_CORE_DB_* via extra={}.
        Verify the merge order: extra wins over the strip."""
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        env = _agent_subprocess_env(
            extra={"IW_CORE_DB_PORT": "39999", "IW_CORE_DB_HOST": "e2e-host"}
        )
        assert env["IW_CORE_DB_PORT"] == "39999"
        assert env["IW_CORE_DB_HOST"] == "e2e-host"


class TestBrowserVerificationEnvStillWins:
    """AC6: existing browser-verification env injection (extra={...})
    still wins after I-00062 snapshot + strip."""

    def test_bv_env_overrides_strip(self, monkeypatch):
        """A bv-style call to _agent_subprocess_env(extra={'IW_CORE_DB_PORT':
        '39999', ...}) returns the e2e port, not stripped, not 5433."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        bv = {
            "IW_CORE_DB_HOST": "e2e-host",
            "IW_CORE_DB_PORT": "39999",
            "IW_CORE_DB_NAME": "iw_orch_e2e",
            "IW_CORE_DB_USER": "e2e_user",
            "IW_CORE_DB_PASSWORD": "e2e_pw",
        }
        env = _agent_subprocess_env(extra=bv)

        assert env["IW_CORE_DB_HOST"] == "e2e-host"
        assert env["IW_CORE_DB_PORT"] == "39999"
        assert env["IW_CORE_DB_NAME"] == "iw_orch_e2e"
        assert env["IW_CORE_DB_USER"] == "e2e_user"
        assert env["IW_CORE_DB_PASSWORD"] == "e2e_pw"
        # Snapshot still happens — guard reference is preserved.
        assert env["IW_CORE_ORCH_DB_PORT"] == "5433"
```

### 2. Launch-step injection integration test (`tests/integration/daemon/test_launch_step_env_isolation.py`)

This file holds the genuine integration coverage of `_launch_step`'s
compose-stack branch. The unit-level coverage of `_agent_subprocess_env`
(snapshot + strip + extra-merge) lives in the file from Section 1; do
NOT duplicate it here.

```python
"""Integration tests for I-00062 — _launch_step env injection."""

from __future__ import annotations

import pytest

# Adapt imports to whatever S03 exposed. If S03 refactored the injection
# block into a `_build_step_env(worktree_info, bv_env=None)` helper,
# import that. Otherwise patch subprocess.Popen and capture env=.


class TestLaunchStepInjectsWorktreeDBEnv:
    """I-00062 AC1: when a worktree has a compose stack, _launch_step
    must inject the per-worktree DB env vars from worktree_info, not
    leave them resolving to the daemon's 5433."""

    def test_compose_stack_injects_all_five_db_vars(self, monkeypatch):
        """Build worktree_info with a fake compose stack and assert the
        agent env has the per-worktree DB vars, not the daemon's.
        Canonical proof of AC1."""
        # See I-00062_S03_Backend_report.md for the exact integration
        # surface S03 chose; adapt the test accordingly.
        ...

    def test_missing_creds_raises_on_compose_stack(self, monkeypatch):
        """Defensive: if compose_path is set but a credential is None,
        _launch_step must raise RuntimeError naming I-00062 — never
        fall back to inherited env."""
        ...
```

For these tests, you'll need to set up a fake `BatchItem` /
`worktree_info` and call the real `_launch_step` (or, if isolation is
hard, refactor S03's injection block into a helper `_build_step_env(
worktree_info, bv_env=None)` and test the helper directly). Coordinate
with S04 review feedback if the surface needs sharpening.

### 3. Fail-fast guard test (`tests/unit/orch_config/test_agent_context_failfast.py`)

These tests cover the guard in isolation. In production the snapshot
in `_agent_subprocess_env` is what makes `IW_CORE_ORCH_DB_PORT` reliably
available in agent contexts — so add a final test (`test_legacy_worktree
_with_inherited_orch_port_raises`) that simulates the legacy regression
flow: snapshot sets ORCH_DB_PORT, worktree's .env then sets DB_PORT to
the same value, guard fires.

```python
"""I-00062 AC3: orch.config refuses to resolve to orch port in agent
context."""

from __future__ import annotations

import pytest

from orch import config


class TestAgentContextFailFast:
    def test_agent_context_with_orch_port_raises(self, monkeypatch):
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        with pytest.raises(RuntimeError, match="I-00062"):
            config.get_db_url()

    def test_agent_context_with_worktree_port_passes(self, monkeypatch):
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "36216")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch")

        url = config.get_db_url()
        assert "36216" in url
        assert "5433" not in url

    def test_operator_context_with_orch_port_passes(self, monkeypatch):
        """Operator (no IW_CORE_AGENT_CONTEXT) is unaffected."""
        monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        url = config.get_db_url()
        assert "5433" in url

    def test_get_orch_db_url_does_not_apply_guard(self, monkeypatch):
        """get_orch_db_url is the legitimate operator channel — it must
        reach 5433 even in agent context."""
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        url = config.get_orch_db_url()
        assert "5433" in url

    def test_runbook_string_in_error_message(self, monkeypatch):
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        with pytest.raises(RuntimeError) as exc_info:
            config.get_db_url()
        # The runbook reference is the operator's escape hatch
        assert "I-00062" in str(exc_info.value)

    def test_legacy_worktree_with_inherited_orch_port_raises(self, monkeypatch):
        """End-to-end semantic: a legacy (no-compose) worktree whose .env
        still mirrors main's IW_CORE_DB_PORT=5433. After
        _agent_subprocess_env's snapshot, IW_CORE_ORCH_DB_PORT=5433 is
        set; load_dotenv from the worktree .env then sets
        IW_CORE_DB_PORT=5433. The guard MUST fire — without the snapshot
        in Layer 1, this test goes vacuous (guard short-circuits).
        Pre-fix: no snapshot, no guard → silent leak. Post-fix: snapshot
        primes ORCH_DB_PORT, guard raises."""
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        # Layer 1 snapshot would set this; we set it directly here to
        # simulate the post-_agent_subprocess_env state.
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        # load_dotenv from the legacy worktree's .env populates these:
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        with pytest.raises(RuntimeError, match="I-00062"):
            config.get_db_url()
```

### 4. Migration round-trip integration test (`tests/integration/db/test_i_00062_migration.py`)

```python
"""I-00062 AC5: migration adds the four columns and is reversible."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect


@pytest.mark.integration
class TestI00062MigrationRoundTrip:
    def test_upgrade_adds_four_columns(self, alembic_engine):
        """After alembic upgrade head, batch_items has the four new
        columns, all nullable."""
        inspector = inspect(alembic_engine)
        cols = {c["name"]: c for c in inspector.get_columns("batch_items")}

        assert "worktree_db_host" in cols
        assert "worktree_db_name" in cols
        assert "worktree_db_user" in cols
        assert "worktree_db_password" in cols

        # All four nullable
        assert cols["worktree_db_host"]["nullable"] is True
        assert cols["worktree_db_name"]["nullable"] is True
        assert cols["worktree_db_user"]["nullable"] is True
        assert cols["worktree_db_password"]["nullable"] is True

    def test_downgrade_drops_four_columns(self, alembic_engine):
        """After alembic downgrade -1 (from I-00062 head), the four
        columns are gone."""
        ...
```

Match the existing fixture style in
`tests/integration/db/test_F00077_migration.py` (or whichever recent
test exercises a single-revision round-trip). If no such fixture exists,
adapt `tests/conftest.py`'s testcontainer setup to spin up postgres,
`alembic upgrade head`, then `alembic downgrade -1` to the prior head.

### 5. Browser-verification env regression (AC6)

The `TestBrowserVerificationEnvStillWins` class lives in
`tests/unit/daemon/test_agent_subprocess_env.py` (Section 1) — it is a
pure-function check on the merge order, not an integration concern. Do
NOT duplicate it in the integration file.

## Project Conventions

Read `tests/CLAUDE.md` for:
- Testcontainer setup patterns (port, env scrubbing)
- `monkeypatch.setenv` / `delenv` usage (NEVER use `importlib.reload`)
- pytest markers (`@pytest.mark.integration` for tests that need a DB
  testcontainer)
- Replace `psycopg2://` with `psycopg://` in testcontainer URLs
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`
  in tests that don't go through alembic

Read `CLAUDE.md` for the docker / migration rules.

## TDD Requirement

These tests should FAIL on the pre-fix code (before S01 + S03 merged) and
PASS after. Specifically:

- `test_strips_inherited_orch_db_vars` — FAILS pre-fix (env contains
  IW_CORE_DB_PORT=5433), PASSES post-fix (key absent).
- `test_snapshots_orch_creds_before_strip` — FAILS pre-fix (no snapshot,
  IW_CORE_ORCH_DB_PORT absent), PASSES post-fix (snapshot populates it).
- `test_compose_stack_injects_all_five_db_vars` — FAILS pre-fix (env
  has 5433), PASSES post-fix (env has worktree port).
- `test_agent_context_with_orch_port_raises` — FAILS pre-fix (no guard
  in get_db_url), PASSES post-fix (RuntimeError raised).
- `test_legacy_worktree_with_inherited_orch_port_raises` — FAILS pre-fix
  twice over (no snapshot, no guard), PASSES post-fix (both layers fire).

Document this in your report — list each test name and its expected pre-
vs post-fix behavior.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. **`make format`** on test files.
2. **`make typecheck`** — zero new errors.
3. **`make lint`** — zero new errors.

**Do NOT run bare `make`.**

## Test Verification (NON-NEGOTIABLE)

Run **all four new test files**:

```bash
uv run pytest tests/unit/daemon/test_agent_subprocess_env.py -v
uv run pytest tests/integration/daemon/test_launch_step_env_isolation.py -v
uv run pytest tests/unit/orch_config/test_agent_context_failfast.py -v
uv run pytest tests/integration/db/test_i_00062_migration.py -v
```

Then run full suites:

```bash
make test-unit
make test-integration
```

Do NOT report `tests_passed: true` unless ALL four new test files pass
AND there are no new failures in `make test-unit` / `make
test-integration`.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "I-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/daemon/test_agent_subprocess_env.py",
    "tests/integration/daemon/test_launch_step_env_isolation.py",
    "tests/unit/orch_config/test_agent_context_failfast.py",
    "tests/integration/db/test_i_00062_migration.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Each new test's pre-fix vs post-fix behavior documented above"
}
```
