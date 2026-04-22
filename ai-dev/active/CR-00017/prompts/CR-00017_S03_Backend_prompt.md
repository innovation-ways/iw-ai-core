# CR-00017_S03_Backend_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits
## ⛔ You MUST NOT run `alembic upgrade head` against the live DB

Your work in this step is to write the **library** that enforces the above at
the Python level. Test it with testcontainer fixtures (see `tests/CLAUDE.md`).
The live DB on port 5433 is strictly off-limits for migration operations
initiated by you.

See `docs/IW_AI_Core_Agent_Constraints.md` (R1 + the new R2 added in S09).

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md` — Design (Desired Behavior point 3, AC1, AC6, AC7)
- `ai-dev/active/CR-00017/reports/CR-00017_S02_CodeReview_report.md` — S01/S02 landed the table
- `orch/db/session.py` — `engine`, `SessionLocal`, `get_db_url()`
- `orch/db/models.py` — has `PendingMigrationLog` now
- `orch/config.py` — env-var loader
- `orch/db/migrations/env.py` — alembic env config
- Alembic API reference (in `uv`'s installed alembic package) — `command.upgrade`, `command.downgrade`, `ScriptDirectory`, `MigrationContext`
- `CLAUDE.md`, `orch/CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S03_Backend_report.md`
- `orch/db/safe_migrate.py` (new)
- `tests/unit/test_safe_migrate.py` (new — unit smoke)

## Context

You're building the library that every migration operation has to go through. It is THE choke-point between agent-context code and DB-mutating alembic calls. Read the design doc carefully — especially Desired Behavior point 3 and AC1.

## Requirements

### 1. Public API

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

class AgentContextForbidden(RuntimeError):
    """Raised when a caller tries to apply/rollback/unfreeze inside an agent subprocess."""

class MultipleHeadsError(RuntimeError):
    """Raised when the alembic revision graph has >1 head — requires a manual merge revision."""

@dataclass(frozen=True)
class Revision:
    id: str
    description: str
    down_revision: str | None

@dataclass(frozen=True)
class DryRunResult:
    revisions_applied: list[str]
    success: bool
    duration_ms: int
    stdout_tail: str
    stderr_tail: str
    error_message: str | None

@dataclass(frozen=True)
class ApplyResult(DryRunResult): ...

@dataclass(frozen=True)
class RollbackResult:
    revision_from: str
    revision_to: str
    success: bool
    duration_ms: int
    error_message: str | None


def _assert_not_agent_context() -> None:
    """Internal: raise AgentContextForbidden if IW_CORE_AGENT_CONTEXT='true'."""


def list_pending_revisions(db_url: str | None = None) -> list[Revision]:
    """Pure: compare alembic ScriptDirectory heads to the DB's current revision.
       Raises MultipleHeadsError if multiple heads in ScriptDirectory.
       Does NOT require agent-context guard — read-only introspection."""


def dry_run(tempdb_url: str, batch_id: int | None = None) -> DryRunResult:
    """Spin up alembic context against tempdb_url, upgrade to head, record log entry.
       tempdb_url is expected to be a testcontainer URL (caller provides).
       Does NOT require agent-context guard — operates on a disposable DB.
       BUT: refuses if tempdb_url matches the live DB URL (sanity check)."""


def apply(live_db_url: str, batch_id: int | None = None) -> ApplyResult:
    """Acquire migration lock, upgrade to head against live DB, release lock.
       RAISES AgentContextForbidden if IW_CORE_AGENT_CONTEXT='true'.
       Records log entry with phase='apply'."""


def rollback(live_db_url: str, steps: int = 1, batch_id: int | None = None) -> RollbackResult:
    """alembic downgrade {-steps} against live DB.
       RAISES AgentContextForbidden if IW_CORE_AGENT_CONTEXT='true'.
       Records log entry with phase='rollback'."""


def current_revision(db_url: str) -> str | None:
    """Read the current revision from the DB's alembic_version table.
       Safe for anyone."""


def is_live_db_url(url: str) -> bool:
    """Return True iff the URL matches the live DB connection from orch.config."""
```

### 2. Guard invariants

- `apply()` and `rollback()` MUST be first-line-guarded: the very first statement checks `IW_CORE_AGENT_CONTEXT`. Before any session creation, before any alembic call.
- `dry_run()` has a secondary guard: if `tempdb_url == live_db_url`, refuse with `ValueError("dry_run called on live DB — refusing")`. Even if an operator, you do NOT dry-run on live.
- `list_pending_revisions()` and `current_revision()` are pure reads — no guards.

### 3. Multi-head detection

Use `alembic.script.ScriptDirectory.from_config()` → `.get_heads()`. If `len(heads) > 1`: raise `MultipleHeadsError` with both heads in the message and the suggested resolution ("create a merge revision with `alembic merge -m 'merge branches X and Y' <head1> <head2>`").

### 4. Log writing

Every `dry_run`, `apply`, and `rollback` call writes to `pending_migration_log` via a fresh short-lived session (don't reuse the caller's session — if it raises mid-op, logging must still work). Capture stdout/stderr of the alembic command via `contextlib.redirect_stdout / redirect_stderr` into string buffers; truncate to the last 16KB; store in `stdout_tail` / `stderr_tail`.

On success: `success=true, completed_at=now(), error_message=None`.
On failure: `success=false, completed_at=now(), error_message=<exception-str>`.

### 5. Alembic programmatic API

Use `alembic.config.Config` + `alembic.command.upgrade(cfg, "head")` / `alembic.command.downgrade(cfg, "-1")`. Configure via `cfg.set_main_option("sqlalchemy.url", db_url)` and `cfg.set_main_option("script_location", "orch/db/migrations")`. This is the non-CLI invocation — no subprocesses.

### 6. Migration lock integration

`apply()` and `rollback()` acquire the `iw migration-lock` as the daemon (not an item). Use `item="CR-00017-runtime"` or `item="daemon"` — whatever convention the daemon uses internally for its own operations. If the lock is held by another item (stale agent), raise a distinct `MigrationLockHeldError` so the daemon's merge pipeline can surface it clearly.

### 7. Unit test smoke

`tests/unit/test_safe_migrate.py`:

- `test_apply_refuses_in_agent_context` — monkeypatch `IW_CORE_AGENT_CONTEXT=true`, call `apply("postgresql+psycopg://unused")`, expect `AgentContextForbidden`.
- `test_rollback_refuses_in_agent_context` — same for `rollback`.
- `test_dry_run_refuses_live_url` — monkeypatch `orch.config.get_db_url()` to return `"postgresql+psycopg://live/db"`, call `dry_run("postgresql+psycopg://live/db")`, expect `ValueError`.
- `test_multiple_heads_raises` — mock `ScriptDirectory.get_heads()` to return `["a", "b"]`, call `list_pending_revisions`, expect `MultipleHeadsError` with both heads in `str(exc)`.
- `test_is_live_db_url_matches_config` — sanity.

Integration tests for the full pipeline (testcontainer-driven) live in S11 — not this step.

### 8. Do NOT wire into the daemon yet

S05 is the daemon integration step. This step ships the library in isolation.

## Project Conventions

- Module placement: `orch/db/safe_migrate.py`.
- Logging via `logging.getLogger(__name__)` — never `print`.
- Type hints on all public signatures.
- Dataclasses frozen.
- No hardcoded URLs or ports.

## TDD Requirement

RED → GREEN → REFACTOR. Write the unit tests first, confirm they fail (module doesn't exist). Then implement. Then refactor for clarity.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all new tests pass.
2. `make lint` — pass.
3. `make test-integration` — regressions elsewhere checked.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00017",
  "completion_status": "complete",
  "files_changed": [
    "orch/db/safe_migrate.py",
    "tests/unit/test_safe_migrate.py"
  ],
  "tests_passed": true,
  "test_summary": "M unit + all existing passing",
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S03
# ...
uv run iw step-done CR-00017 --step S03 --report ai-dev/active/CR-00017/reports/CR-00017_S03_Backend_report.md
```
