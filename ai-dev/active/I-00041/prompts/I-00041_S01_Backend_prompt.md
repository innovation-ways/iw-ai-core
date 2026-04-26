# I-00041_S01_Backend_prompt

**Work Item**: I-00041 — Connection-layer guard against integration tests writing to the live orchestration DB
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following or any command that changes Docker
container/volume/network state: `docker kill | stop | rm | restart |
compose up/down/restart | volume rm/prune | system/container/image prune`.
Allowed: testcontainers spun up by pytest fixtures, read-only introspection
(`docker ps`, `docker inspect`, `docker logs`), and invoking `./ai-core.sh` /
`make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live
orchestration DB (port 5433) from an agent context. This step adds NO new
migration — pure runtime guard wiring.

## Input Files

- `ai-dev/active/I-00041/I-00041_Issue_Design.md`
- `orch/db/session.py`
- `orch/db/safe_migrate.py`
- `orch/db/identity.py`
- `orch/db/models.py`
- `orch/config.py`

## Output Files

- New: `orch/db/live_db_guard.py`
- Modified: `orch/db/session.py`
- Modified: `orch/db/safe_migrate.py`
- Modified: `orch/daemon/main.py` (route `create_session_factory` line 64 through `safe_create_engine`)
- Modified: `orch/daemon/migration_pipeline.py` (route lines 231, 266 through `safe_create_engine`)
- Modified: `orch/daemon/migration_rebase.py` (route lines 210, 239 through `safe_create_engine`)
- Modified: `orch/daemon/worktree_compose.py` (route line 224 through `safe_create_engine`)
- Modified: `orch/cli/merge_queue_commands.py` (route line 51 through `safe_create_engine`)
- Report: `ai-dev/active/I-00041/reports/I-00041_S01_Backend_report.md`

## Context

You are implementing the **connection-layer chokepoint** that prevents
unauthorised writes to the live orchestration DB on port 5433. The bug:
integration tests can currently mutate live operational state because
the only existing guard (`_assert_not_agent_context` in `safe_migrate.py`)
is opt-out, lives at the wrong layer, and is bypassed by helpers that
call `create_engine(get_db_url())` directly. See the design doc for the
full root-cause and the runaway-pytest incident that motivated this issue.

This step adds the chokepoint. Step S03 will invert the test conftest
polarity and wire up the operator/daemon opt-in env vars. Step S05 writes
the reproduction and regression tests.

Read the design doc first, then `CLAUDE.md`, then `orch/db/identity.py`
(the canonical "fail-fast at boot" pattern this guard mirrors).

## Requirements

### R1 — `orch/db/live_db_guard.py` (new module)

Public surface:

```python
class LiveDbConnectionRefused(RuntimeError):
    """Raised when a connection to the live orch DB is attempted from a
    refused context (test, deprecated agent, or no opt-in)."""

def is_live_db_url(url: str) -> bool:
    """Return True if `url` resolves to the live orch DB.
    Match priority: (1) instance-fingerprint match against
    IW_CORE_EXPECTED_INSTANCE_ID; (2) host:port match against the values
    in os.environ['IW_CORE_DB_HOST'] / ['IW_CORE_DB_PORT'].
    Fingerprint is the primary check; host:port is the fallback when
    EXPECTED_INSTANCE_ID is unset (e.g. early in bootstrap) or when the
    fingerprint cannot be read because the DB is unreachable.
    Returns False on parse failures (fail-open for non-PG URLs)."""

def assert_engine_url_allowed(url: str) -> None:
    """Raise LiveDbConnectionRefused if `url` is the live orch DB AND
    the caller is in a refused context.

    Decision matrix (evaluated top-to-bottom, first match wins):
      1. URL is NOT the live DB                    → ALLOW (no-op)
      2. Any allowed-context flag is set           → ALLOW (operator/daemon)
            - IW_CORE_OPERATOR_APPLY=true (`iw migrations apply`)
            - IW_CORE_DAEMON_CONTEXT=true (daemon entry point)
      3. Any refused-context flag is set           → REFUSE (raise)
            - IW_CORE_TEST_CONTEXT=true (pytest conftest)
            - IW_CORE_AGENT_CONTEXT=true (deprecated alias)
      4. No flags set                              → ALLOW (ad-hoc local scripts)

    Allowed-context wins over refused-context (rule 2 before rule 3).
    Rationale: an operator running daemon code locally inside a pytest
    sub-shell is intentional; the operator's explicit opt-in is more
    specific than the inherited test-context default.

    Error message MUST include all three:
      - the URL host:port (operator needs to see the offending target)
      - the active refused-context flag name (operator needs to know
        which flag is set)
      - the remediation hint: 'set IW_CORE_OPERATOR_APPLY=true via
        `iw migrations apply --i-am-operator` or run from the daemon entry
        point (which sets IW_CORE_DAEMON_CONTEXT=true)'
    """
```

Implementation notes:
- Use `sqlalchemy.engine.url.make_url(url)` for parsing — NOT regex.
- Fingerprint comparison uses the existing helper in `orch/db/identity.py`.
  Read `IW_CORE_EXPECTED_INSTANCE_ID` from env. Do NOT open a connection
  to compute the fingerprint of the candidate URL — that would defeat the
  guard. Compare the candidate URL's host:port against
  `os.environ.get('IW_CORE_DB_HOST', 'localhost')` +
  `os.environ.get('IW_CORE_DB_PORT', '5433')`. The `EXPECTED_INSTANCE_ID`
  is treated as the authoritative declaration of "the live DB is the one
  whose fingerprint matches X" — we don't probe.
- All env-var reads happen at call time, not at import time. Never cache.
- Logger name: `orch.db.live_db_guard`.
- No state, no globals beyond the env-var reads.

### R2 — Wire the guard into `orch/db/session.py`

The current file (line ~34) creates `engine` at module top-level via
`engine = create_engine(get_db_url(), ...)`. That has to change because
S03 will arm `IW_CORE_TEST_CONTEXT=true` session-wide in pytest, and
test code that transitively imports `orch.db.session` must not be
refused at import time (it would break collection of unrelated tests).

Make engine creation **lazy via module `__getattr__`** so the public
names `engine` and `SessionLocal` continue to work, but actual engine
construction (and the guard call inside it) is deferred until the
attribute is first accessed.

Concretely:

1. Add a thin helper, `safe_create_engine(url, **kwargs) -> Engine`, that
   calls `assert_engine_url_allowed(url)` first, then
   `create_engine(url, **kwargs)`. Export it from `orch.db.session`. All
   other modules that need to build engines call this instead of raw
   `create_engine`.

2. Replace the top-level `engine = create_engine(...)` and
   `SessionLocal = sessionmaker(bind=engine, ...)` with module-level
   private holders and a `__getattr__`:

   ```python
   _engine: Engine | None = None
   _session_local: sessionmaker | None = None

   def _get_engine() -> Engine:
       global _engine
       if _engine is None:
           _engine = safe_create_engine(
               get_db_url(),
               pool_pre_ping=True,
               pool_size=get_db_pool_size(),
               max_overflow=get_db_max_overflow(),
               pool_recycle=1800,
               pool_timeout=10,
           )
       return _engine

   def _get_session_local() -> sessionmaker:
       global _session_local
       if _session_local is None:
           _session_local = sessionmaker(
               bind=_get_engine(), autocommit=False, autoflush=False,
           )
       return _session_local

   def __getattr__(name: str) -> object:
       if name == "engine":
           return _get_engine()
       if name == "SessionLocal":
           return _get_session_local()
       raise AttributeError(
           f"module 'orch.db.session' has no attribute {name!r}"
       )
   ```

3. `get_session()` keeps its current signature; internally call
   `_get_session_local()()` instead of `SessionLocal()`.

4. The **guard fires at first attribute access**, not at module import.
   `import orch.db.session` is therefore safe under any context flags.
   `from orch.db.session import engine` (or any code that uses `engine` /
   `SessionLocal`) triggers lazy creation, which calls the guard, which
   refuses if the URL is the live DB and a refused-context flag is set.

### R3 — Route every `create_engine` call in `orch/` through the chokepoint

The design's invariant is **single chokepoint discipline**: every engine
creation in `orch/` goes through `safe_create_engine`. Find every
`create_engine(...)` call below and replace with `safe_create_engine(...)`
imported from `orch.db.session`. Verify the full set with:

```bash
grep -rnE "create_engine\(" orch/ --include='*.py' | grep -v live_db_guard | grep -v session.py
```

Expected post-fix: only `safe_create_engine` matches (the new chokepoint
itself is in `session.py`, which is excluded).

#### R3.1 — `orch/db/safe_migrate.py` (4 sites + alembic config)

- `_current_revision_from_db` line 170 (read-only but still goes through the chokepoint)
- `_write_migration_log` line 200 — **this is the bypass that caused the live-DB writes**
- `_acquire_migration_lock` line 312
- `_release_migration_lock` line 346
- `_build_alembic_config` (the alembic config sets `sqlalchemy.url`; the
  config builder itself doesn't open a connection, but any subsequent
  `command.upgrade/downgrade(cfg, ...)` will. Add a defensive call to
  `assert_engine_url_allowed(url)` inside `_build_alembic_config` so that
  the refusal fires before alembic's own engine creation.)

#### R3.2 — `orch/daemon/main.py` (1 site)

- `create_session_factory` line 64 — this is the daemon's primary
  session-factory builder. Routing it through the chokepoint means the
  daemon's own DB access is gated by the same logic; once
  `IW_CORE_DAEMON_CONTEXT=true` is armed (S03 R2), it is allowed.

#### R3.3 — `orch/daemon/migration_pipeline.py` (2 sites)

- Line 231 (`is_merge_queue_frozen` reader)
- Line 266 (`set_merge_queue_frozen` writer)

#### R3.4 — `orch/daemon/migration_rebase.py` (2 sites)

- Lines 210 and 239 — both in the pre-merge rebase phase (CR-00021).
  These run under daemon context and will be allowed once armed.

#### R3.5 — `orch/daemon/worktree_compose.py` (1 site)

- Line 224 inside `_emit_event` — short-lived session for the
  daemon-event write.

#### R3.6 — `orch/cli/merge_queue_commands.py` (1 site)

- Line 51 — operator CLI command. Operator runs without an opt-in
  flag, so the guard's "no flag set → allowed" default-allow path
  preserves current behaviour.

For each replacement, preserve the `pool_pre_ping=True` and any other
kwargs that are currently passed. Add `from orch.db.session import
safe_create_engine` at the top of each file (or inside the function body
where the existing `from sqlalchemy import create_engine` lives — match
local style).

### R4 — Deprecate `_assert_not_agent_context`

Keep the function — do NOT delete. Make it a thin delegator:

```python
def _assert_not_agent_context(url: str) -> None:
    """DEPRECATED: use orch.db.live_db_guard.assert_engine_url_allowed.

    Retained for backwards compatibility with any in-flight branches.
    Will be removed in a follow-up incident no earlier than 2026-05-26.
    """
    import warnings  # noqa: PLC0415
    warnings.warn(
        "_assert_not_agent_context is deprecated; use "
        "orch.db.live_db_guard.assert_engine_url_allowed",
        DeprecationWarning,
        stacklevel=2,
    )
    from orch.db.live_db_guard import assert_engine_url_allowed  # noqa: PLC0415
    assert_engine_url_allowed(url)
```

Existing callers in `safe_migrate.py` (`apply`, `rollback`, `dry_run`)
that still call `_assert_not_agent_context(...)` continue to work because
the new guard is at least as strict in the contexts those callers were
designed for. Add a TODO comment at each call site noting they can be
removed once R3 routes those flows through `safe_create_engine`.

### R5 — Backwards compatibility

- The new module MUST NOT import from `orch/daemon/` or `dashboard/` (one-way
  dependency: daemon/dashboard → orch.db, never reverse).
- Public API of `orch/db/session.py` (existing names: `engine`, `SessionLocal`,
  `get_session`) MUST remain importable with the same signatures. Internal
  changes only.
- The new module is pure stdlib + sqlalchemy. No new third-party deps.
- No alembic migration file. This is a pure runtime change.

## Project Conventions

Read the project's `CLAUDE.md` for architecture, layer boundaries, and the
critical rules (NEVER mock the database in integration tests; NEVER reload
config in tests; the orch DB is sacred).

- Type hints everywhere. `from __future__ import annotations` at top of new
  files.
- Use `sqlalchemy.engine.url.make_url` for URL parsing.
- Logger configuration follows the existing pattern in `orch/db/identity.py`.
- No `print()`. No bare `except:`. Specific exception types.
- No new comments unless the WHY is genuinely non-obvious (e.g. the
  fingerprint-vs-host:port priority — that warrants one comment).

## TDD Requirement

S05 (Tests) writes the full unit/integration suite. For S01, write the **shape
contract** for the new module: a smoke check in your report showing each
public function imports cleanly and the docstrings are present. Do NOT
write the unit tests — those belong to S05.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make lint` — must pass.
2. `make typecheck` — must pass.
3. `uv run python -c "from orch.db.live_db_guard import LiveDbConnectionRefused,
   is_live_db_url, assert_engine_url_allowed; print('imports ok')"` — must
   print `imports ok`.
4. `uv run python -c "from orch.db.session import safe_create_engine, engine,
   SessionLocal, get_session; print('session ok')"` — must print `session ok`.
5. Confirm `import orch.db.session` does NOT trigger the guard:
   ```bash
   IW_CORE_TEST_CONTEXT=true uv run python -c "import orch.db.session; print('import-only ok')"
   ```
   Must print `import-only ok` (lazy `__getattr__` defers construction).
6. Confirm `from orch.db.session import engine` DOES trigger the guard
   under test context against a live URL:
   ```bash
   IW_CORE_TEST_CONTEXT=true IW_CORE_DB_HOST=localhost IW_CORE_DB_PORT=5433 \
     uv run python -c "from orch.db.session import engine; engine"
   ```
   Must exit non-zero with `LiveDbConnectionRefused`.
7. **Single-chokepoint discipline check** (the canonical post-fix invariant):
   ```bash
   grep -rnE "create_engine\(" orch/ --include='*.py' \
     | grep -v "live_db_guard" \
     | grep -v "safe_create_engine"
   ```
   Must show ONE match — the chokepoint itself in `orch/db/session.py`
   inside `safe_create_engine`'s body. Any other match is a missed
   call site and a regression of the chokepoint invariant.
8. Operator-vs-test priority smoke (locks the M1 priority decision):
   ```bash
   IW_CORE_OPERATOR_APPLY=true IW_CORE_TEST_CONTEXT=true \
   IW_CORE_DB_HOST=localhost IW_CORE_DB_PORT=5433 \
   uv run python -c "
   from orch.db.live_db_guard import assert_engine_url_allowed
   assert_engine_url_allowed('postgresql://x:y@localhost:5433/iw_orch')
   print('operator wins ok')
   "
   ```
   Must print `operator wins ok` (operator allow-list beats test
   refused-context).

Report: `tests_passed: true` only if all eight checks pass.

## Subagent Result Contract

When complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00041",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/live_db_guard.py",
    "orch/db/session.py",
    "orch/db/safe_migrate.py",
    "orch/daemon/main.py",
    "orch/daemon/migration_pipeline.py",
    "orch/daemon/migration_rebase.py",
    "orch/daemon/worktree_compose.py",
    "orch/cli/merge_queue_commands.py"
  ],
  "tests_passed": true,
  "test_summary": "lint OK, typecheck OK, imports OK, single-chokepoint grep clean, operator-wins priority OK",
  "blockers": [],
  "notes": ""
}
```

## Lifecycle Commands

When you START:
```bash
uv run iw step-start I-00041 --step S01
```

When you COMPLETE:
```bash
mkdir -p ai-dev/active/I-00041/reports
uv run iw step-done I-00041 --step S01 --report ai-dev/active/I-00041/reports/I-00041_S01_Backend_report.md
```

If blocked:
```bash
uv run iw step-fail I-00041 --step S01 --reason "<one-line cause>"
```
