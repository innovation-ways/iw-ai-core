# F-00074_S02_Backend_prompt

**Work Item**: F-00074 — Keep-Alive Scheduler
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. Testcontainer fixtures are exempt from the Docker restriction.

## Input Files

- `ai-dev/active/F-00074/F-00074_Feature_Design.md` — read first
- `ai-dev/active/F-00074/reports/F-00074_S01_Database_report.md` — S01 output (migration revision, model names)
- `orch/db/models.py` — the three new models added by S01
- `orch/daemon/main.py` — daemon main loop; find `_poll_cycle()` and the poll-count pattern
- `orch/daemon/doc_job_poller.py` — canonical poller class pattern to follow
- `orch/daemon/batch_manager.py` — claude CLI subprocess invocation pattern (line ~972)
- `orch/db/session.py` — `SessionLocal` and session management

## Output Files

- New: `orch/keep_alive_service.py`
- New: `orch/daemon/keep_alive_poller.py`
- Modified: `orch/daemon/main.py` (import + wire poller)
- `ai-dev/active/F-00074/reports/F-00074_S02_Backend_report.md`

## Context

Implement the business logic for the Keep-Alive Scheduler. No API routes (S04), no templates (S05). The service handles all DB operations and the subprocess invocation. The poller calls the service on a ~60-second cadence inside the daemon's existing poll loop.

## Requirements

### 1. `orch/keep_alive_service.py`

#### Message pool

Define at module level (not configurable via UI):

```python
_MESSAGES = [
    "Hi! How are you doing today?",
    "Hello there! Anything interesting going on?",
    "Hey! Just checking in.",
    "Good to connect! What's new?",
    "Hi! Hope you're having a great day.",
    "Hello! Ready for some interesting work?",
    "Hey there! What shall we explore today?",
    "Greetings! How can I help?",
    "Hi! Everything going well?",
    "Hello! Just a quick hello from the scheduler.",
    "Hey! Keeping the connection warm.",
    "Hi! What's on your mind?",
    "Good to hear from you! All good here.",
    "Hello! Just popping in to say hi.",
    "Hey! The day is going well, I hope.",
]

def pick_message() -> str:
    return random.choice(_MESSAGES)
```

#### Config CRUD

```python
def get_config(db: Session) -> KeepAliveConfig:
    """Return the singleton config row (id=1). Creates it with defaults if missing."""

def upsert_config(db: Session, model: str, window_duration_hours: int) -> KeepAliveConfig:
    """Update the singleton. Uses INSERT … ON CONFLICT DO UPDATE or SELECT + update."""
```

#### Slot CRUD

```python
def list_slots(db: Session) -> list[KeepAliveSlot]:
    """Return all slots ordered by time_hhmm."""

def add_slot(db: Session, time_hhmm: str) -> KeepAliveSlot:
    """
    Validate time_hhmm format ("HH:MM", 00:00–23:59).
    Raise ValueError on invalid format.
    Raise IntegrityError (from DB) on duplicate — let the router handle it.
    Link to config_id=1.
    """

def delete_slot(db: Session, slot_id: int) -> bool:
    """Delete slot. Returns False if not found."""

def toggle_slot(db: Session, slot_id: int) -> KeepAliveSlot | None:
    """Flip enabled. Returns updated slot or None if not found."""
```

#### Due-slot detection

```python
def get_due_slots(db: Session) -> list[KeepAliveSlot]:
    """
    Return enabled slots that should fire right now.

    A slot is due when ALL of:
    1. slot.enabled is True
    2. slot.time_hhmm parsed as today's local datetime falls within [now - 30min, now]
    3. No KeepAliveRun exists for today (calendar day, local time) with this slot's
       time_hhmm AND status in ('success', 'retried_success')

    Uses datetime.now() (no timezone — local time, matching user's schedule intent).
    """
```

#### Run logging

```python
def log_run(
    db: Session,
    slot_id: int | None,
    slot_time: str,
    status: str,
    error: str | None = None,
) -> KeepAliveRun:
    """Insert a KeepAliveRun row. status must be one of the four defined values."""

def get_recent_runs(db: Session, limit: int = 10) -> list[KeepAliveRun]:
    """Return most recent runs ordered by fired_at DESC, limit rows."""
```

#### Fire function

```python
def fire_claude(message: str, timeout: int = 30) -> tuple[bool, str | None]:
    """
    Spawn: subprocess.run(["claude", "-p", message], capture_output=True, text=True, timeout=timeout)
    Returns (True, None) on returncode==0.
    Returns (False, stderr_or_exception_str) on failure.
    Does NOT retry — retry logic is in the poller.
    subprocess.TimeoutExpired → treat as failure.
    """
```

### 2. `orch/daemon/keep_alive_poller.py`

Pattern: follow `orch/daemon/doc_job_poller.py` exactly.

```python
class KeepAlivePoller:
    def __init__(self) -> None:
        pass  # stateless; session opened per poll call

    def poll(self) -> None:
        """
        Called by the daemon every ~60 s.
        For each due slot (from get_due_slots):
          1. Pick a random message.
          2. Call fire_claude(message).
          3. If success: log_run(status='success').
          4. If failure: retry once with a new random message.
             - Retry success → log_run(status='retried_success').
             - Retry failure → log_run(status='retried_failed', error=combined_errors).
        Each slot is processed independently; one slot's failure does NOT stop others.
        Open a fresh DB session per poll() call (use SessionLocal() context manager).
        Log outcomes via stdlib logging (logger name: 'orch.keep_alive').
        """
```

### 3. Wire into `orch/daemon/main.py`

Locate `_poll_cycle()`. Find the pattern used for periodic checks (e.g., `self._poll_count - self._last_reap_poll_count >= 5`). Add:

```python
# Near daemon __init__ or _startup():
self._keep_alive_poller = KeepAlivePoller()
self._last_keep_alive_poll_count: int = 0

# In _poll_cycle(), after the existing periodic checks:
if self._poll_count - self._last_keep_alive_poll_count >= 6:
    self._last_keep_alive_poll_count = self._poll_count
    try:
        self._keep_alive_poller.poll()
    except Exception:
        logger.exception("KeepAlivePoller.poll() raised unexpectedly")
```

The daemon's default poll interval is ~10 s, so 6 ticks ≈ 60 s.

### 4. Import hygiene

- `orch/keep_alive_service.py`: imports from `orch.db.models` (the three new models), `orch.db.session`, `sqlalchemy.orm.Session`, `datetime`, `random`, `subprocess`, `logging`.
- `orch/daemon/keep_alive_poller.py`: imports `KeepAliveService` functions from `orch.keep_alive_service`, `SessionLocal` from `orch.db.session`, `logging`.
- `orch/daemon/main.py`: add `from orch.daemon.keep_alive_poller import KeepAlivePoller`.

## Project Conventions

- No mocking the DB in integration tests — FOR UPDATE locking can't be tested otherwise.
- Use `datetime.now()` (local, no tz) for slot comparison — times are local per design.
- Never hardcode ports, URLs, or credentials.
- `subprocess.run()` (not `Popen`) for the fire function — we wait for completion.
- Subprocess timeout: 30 seconds (keep-alive should complete in under a second; the timeout is a safety guard).

## TDD Requirement

RED-GREEN-REFACTOR:
1. Write unit tests for `get_due_slots` logic first (mock the DB query results).
2. Write unit tests for `fire_claude` (mock subprocess.run).
3. Confirm RED, implement, confirm GREEN.

## Pre-flight Quality Gates

1. `make format`
2. `make lint`
3. `make typecheck`
4. `make test-unit` — must pass (new tests written in this step or flagged for S06)

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "backend-impl",
  "work_item": "F-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/keep_alive_service.py",
    "orch/daemon/keep_alive_poller.py",
    "orch/daemon/main.py"
  ],
  "preflight": {"format": "ok", "lint": "ok", "typecheck": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
