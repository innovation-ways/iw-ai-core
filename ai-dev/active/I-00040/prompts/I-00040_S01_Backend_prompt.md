# I-00040 S01 — Backend implementation: alembic-version guard helper + wiring

You are executing step **S01** for work item **I-00040** ("Alembic-version guard at daemon/dashboard/launch boundaries").

## ⛔ Docker / Migrations off-limits

Standard rules. Do **NOT** run `alembic upgrade/downgrade/stamp` against the
live orch DB. Do **NOT** add a new alembic migration file — this issue
deliberately does not introduce schema changes. See
`docs/IW_AI_Core_Agent_Constraints.md`.

## Context

The orchestration daemon and the FastAPI dashboard have no startup-time
check that the live orch DB's `alembic_version` matches the head of
`orch/db/migrations/versions/`. When a migration is merged to `main`
but never applied to the live DB, both processes start cleanly, then
fail silently for hours: SQLAlchemy raises `UndefinedColumn` on every
poll, the dashboard 500s, and downstream side-effects corrupt batch
state. See `ai-dev/active/I-00040/I-00040_Issue_Design.md` for the full
write-up — read the **Description**, **Steps to Reproduce**, **Root
Cause Analysis**, and **Acceptance Criteria** sections before coding.

## Project Context

Read `CLAUDE.md` and `orch/CLAUDE.md` for architecture and conventions.
Most relevantly:

- `orch/db/safe_migrate.py` already exposes `list_pending_revisions(db_url)`
  (raises `MultipleHeadsError` on >1 head) and `current_revision(db_url)`.
  Reuse them.
- `orch/db/identity.py` is the canonical pattern for a fail-fast DB
  precondition. Mirror its style: a small module with a public
  `assert_*` function that raises a typed exception, plus a `check_*`
  function that returns a status dataclass.
- The daemon entry point is `orch/daemon/__main__.py` /
  `orch/daemon/main.py`. The dashboard factory is
  `dashboard/app.py::create_app`. Item launch happens in
  `orch/daemon/batch_manager.py::_launch_item` (around line 300, just
  before `worktree_compose.up()` is called).

## Requirements

### R1 — New helper module `orch/db/alembic_guard.py`

Public API (use type hints, docstrings, and `from __future__ import
annotations` per project convention):

```python
@dataclass(frozen=True)
class GuardStatus:
    current_rev: str | None
    head_rev: str | None
    pending: list[str]            # ordered, head-first
    multiple_heads: list[str]     # empty if exactly one head
    ok: bool                      # True iff len(pending) == 0 and len(multiple_heads) <= 1


class DBBehindHeadError(RuntimeError):
    """Raised when alembic_version != ScriptDirectory head."""


class MultipleHeadsError(RuntimeError):
    """Raised when ScriptDirectory has >1 head (re-export from safe_migrate
    or wrap with a clearer message)."""


def check_db_at_head(db_url: str | None = None) -> GuardStatus: ...


def assert_db_at_head(db_url: str | None = None) -> None:
    """Raises DBBehindHeadError or MultipleHeadsError on mismatch.
    Silently returns on match. The error message MUST contain:
      - the current DB revision (or 'EMPTY' if alembic_version is empty)
      - the head revision
      - the literal string 'make db-migrate'
    """


def remediation_message(status: GuardStatus) -> str:
    """Human-readable single-line message used by daemon log, dashboard
    banner, and BatchItem.notes. MUST contain current_rev, head_rev, and
    'make db-migrate'."""
```

Internally this module wraps `orch.db.safe_migrate.list_pending_revisions`
and `current_revision`. Do NOT re-implement the alembic introspection;
delegate.

### R2 — Daemon startup guard in `orch/daemon/main.py`

Add a startup hook **before** the polling loop begins. On
`DBBehindHeadError` or `MultipleHeadsError`:

1. `logger.critical(remediation_message(status))`
2. Emit a `DaemonEvent` of `event_type="db_schema_mismatch"` with
   `event_metadata={"current_rev": ..., "head_rev": ..., "pending":
   [...]}` and `message=remediation_message(status)`.
3. `sys.exit(2)` (use a distinct exit code so the supervisor /
   `./ai-core.sh status` can distinguish it from other failures).

The guard MUST run AFTER `verify_instance_identity` (so the operator
hears about the most-fundamental problem first) and BEFORE the daemon
opens any other work.

### R3 — Dashboard guard in `dashboard/app.py::create_app`

The dashboard MUST NOT refuse to serve — operators need read access to
history pages to diagnose. Instead:

1. At app construction, call `check_db_at_head()` once. Store the
   `GuardStatus` on `app.state.alembic_guard_status`.
2. Register a tiny middleware that, **on every request**:
   - Re-checks **at most once every 10 seconds** (cheap throttle; the
     mismatch is rare and the request hot-path matters more than
     instant detection). Use a module-level lock + timestamp.
   - Updates `app.state.alembic_guard_status` if the throttle window
     has elapsed.
   - Stores the current status on `request.state.alembic_guard_status`
     so the template can read it via the existing Jinja `request`
     proxy.
3. Provide a `dashboard/utils/alembic_guard.py` (or place inside
   `dashboard/middlewares/alembic_guard.py`) helper:
   `is_db_stale(request) -> bool` for use in templates / route guards.
4. Add a small route guard utility `require_db_at_head` (FastAPI
   dependency) that returns HTTP 503 with the remediation message for
   any **state-mutating** endpoint when the DB is stale. Apply it to
   the `/batches/*/approve`, `/batches/*/items/*/launch`, and
   `/items/*/approve` routes (use `Grep` to find them).

### R4 — Launch-time guard in `orch/daemon/batch_manager.py::_launch_item`

Re-check **before any worktree is created** (i.e. before the first
filesystem mutation):

```python
status = check_db_at_head()
if not status.ok:
    batch_item.status = BatchItemStatus.setup_failed
    batch_item.notes = remediation_message(status)
    db.commit()
    _emit_event(
        db, self.project_id, "item_failed", item_id, "work_item",
        remediation_message(status),
        {"phase": "alembic_guard", "reason": "db_behind_head",
         "current_rev": status.current_rev, "head_rev": status.head_rev,
         "pending": status.pending},
    )
    return
```

The guard MUST run before `worktree_setup`, before
`worktree_compose.up`, and before any `os.makedirs` in `.worktrees/`.

### R5 — Backwards compatibility / safety

- Existing callers of `safe_migrate.list_pending_revisions` are
  unaffected. Do not change its signature.
- The new module MUST NOT import from `dashboard/` (one-way dependency:
  dashboard → orch, never the reverse).
- The startup guard MUST be skippable via env var
  `IW_CORE_SKIP_ALEMBIC_GUARD=true` for emergency operator override.
  Log `WARNING` when the override is used. Do NOT honour it from inside
  agent context (`IW_CORE_AGENT_CONTEXT=true` already exists per
  `safe_migrate._assert_not_agent_context` — a similar check applies
  here: the override is operator-only).

### R6 — Logging and observability

- All log lines from this module use logger `orch.db.alembic_guard`.
- The daemon's stderr message on mismatch MUST be a single line
  beginning with `CRITICAL: orch DB schema mismatch — ` followed by
  `current_rev=<rev> head_rev=<rev> run 'make db-migrate' to fix`.
- Every detection emits one `DaemonEvent`. Avoid spamming: dedupe
  consecutive identical mismatches within a 60-second window.

## Constraints

1. Helpers in `orch/db/safe_migrate.py` MUST be reused — do not
   re-implement alembic introspection.
2. NO new alembic migration files in this issue.
3. The dashboard MUST keep serving on mismatch (read-only mode); only
   write actions are blocked.
4. The daemon MUST refuse to start (exit non-zero) on mismatch.
5. Helper code MUST have type hints and short docstrings; NO
   multi-paragraph docstrings.
6. Touch only the files listed in the design's **Code Changes**
   section. If you find another natural place to wire the guard,
   surface it in your report and get approval before adding it.

## Input Files

- `ai-dev/active/I-00040/I-00040_Issue_Design.md` (this work item)
- `orch/db/safe_migrate.py` (existing helpers)
- `orch/db/identity.py` (style template)
- `orch/daemon/main.py` (startup wiring point)
- `orch/daemon/batch_manager.py` (launch-time wiring point)
- `dashboard/app.py` (create_app wiring point)
- `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`

## Output Files

- `orch/db/alembic_guard.py` — new helper module
- `orch/daemon/main.py` — startup hook added
- `orch/daemon/batch_manager.py` — `_launch_item` guard added
- `dashboard/app.py` — `create_app` hook + middleware registered
- `dashboard/utils/alembic_guard.py` (or `dashboard/middlewares/alembic_guard.py`) — request helper + middleware
- `ai-dev/active/I-00040/reports/I-00040_S01_Backend_report.md` — what changed, file list, any deviations

## Lifecycle Commands

When you START:
```bash
uv run iw step-start I-00040 --step S01
```

When you COMPLETE successfully:
```bash
mkdir -p ai-dev/active/I-00040/reports
uv run iw step-done I-00040 --step S01 --report ai-dev/active/I-00040/reports/I-00040_S01_Backend_report.md
```

If FAIL:
```bash
uv run iw step-fail I-00040 --step S01 --reason "brief reason"
```

You MUST call step-done (with --report) or step-fail before exiting.
