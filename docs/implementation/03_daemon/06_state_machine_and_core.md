# Step 06: Daemon State Machine & Core Loop

## Context

The CLI is complete. Now build the daemon — the always-running process that orchestrates all agent execution. Start with the state machine (transition validation) and the core loop (startup, shutdown, signal handling, project registry).

Read these documents:
- `IW_AI_Core_Daemon_Design.md` — sections 2 (process lifecycle), 3 (main loop), 6 (project config reload), 9 (interruptible sleep)
- `IW_AI_Core_Database_Schema.md` — section 3 (all state machines)

## Task

### 1. State Machine (`orch/daemon/state_machine.py`)

Implement transition validation for ALL entity types:

- `WorkItemStatus`: valid transitions (see Database Schema doc section 3.1)
- `WorkItemPhase`: valid transitions (section 3.2)
- `StepStatus`: valid transitions (section 3.3)
- `RunStatus`: valid transitions (section 3.4)
- `BatchStatus`: valid transitions (section 3.5)
- `BatchItemStatus`: valid transitions (section 3.6)

Each should have a `can_transition(from_status, to_status) -> bool` function and a `validate_transition(from_status, to_status)` function that raises `InvalidTransition` with a clear message.

### 2. Project Registry (`orch/daemon/project_registry.py`)

- Load `projects.toml` (stdlib `tomllib` in Python 3.12+)
- For each entry: read `.iw-orch.json` from the project path, validate config
- Register/update project in DB (`INSERT ... ON CONFLICT UPDATE`)
- Detect additions, removals, and disablements on reload
- Track file mtime for change detection

### 3. Daemon Main Class (`orch/daemon/main.py`)

Implement the `Daemon` class with:

- `__init__()`: load config, create DB session factory, initialize empty project/manager dicts
- `run()`: setup signal handlers → startup → main loop → shutdown
- `_startup()`: write PID file, connect to DB, load projects, run startup health check, emit `daemon_started`
- `_poll_cycle()`: reload projects if stale → per-project processing (stub calls to BatchManager) → cross-project services
- `_shutdown()`: emit `daemon_stopped`, remove PID file, close DB
- `_sleep()`: use `threading.Event.wait()` for interruptible sleep (not `time.sleep()`)
- Signal handlers: SIGTERM/SIGINT → set `_running = False` + wake from sleep; SIGHUP → trigger project reload

**Per-project error isolation**: each project's processing is wrapped in try/except. One project's error doesn't block others.

**Main loop error handling**: the entire poll cycle is wrapped in try/except. An unhandled error is logged and the daemon continues to the next cycle. The daemon NEVER crashes from a single poll failure.

### 4. Startup Health Check (`orch/daemon/main.py`)

On startup, detect inconsistencies from previous crashes:
- Query `step_runs WHERE status='running'` — check each PID alive
- Dead PIDs → mark as failed with "Daemon restarted — process was dead"
- Log findings, emit `orphan_detected` events
- Do NOT auto-cleanup worktrees — just report

### 5. Event Emitter

Helper function used throughout the daemon:
```python
def emit_event(db, project_id, event_type, entity_id=None, message=None, metadata=None):
    event = DaemonEvent(project_id=project_id, event_type=event_type, ...)
    db.add(event)
    db.commit()
```

### 6. CLI Integration

Update `iw daemon start` to call `Daemon(config).run()` (foreground mode) or spawn as a background process.

### 7. Tests (TDD)

**Unit tests** (`tests/unit/test_state_machine.py`):
- Test EVERY valid transition for each entity type (parameterized)
- Test EVERY invalid transition is rejected with clear message
- Test edge cases: same-status transition (should reject)

**Unit tests** (`tests/unit/test_project_registry.py`):
- Test: parse valid projects.toml
- Test: detect new project added
- Test: detect project removed
- Test: detect project disabled
- Test: invalid .iw-orch.json → clear error, project skipped

**Unit tests** (`tests/unit/test_daemon_core.py`):
- Test: startup detects stale PID file with dead process → cleans up
- Test: startup detects live PID → exits with error
- Test: signal handling sets _running = False
- Test: per-project error isolation (mock one project to throw, verify others still process)
- Test: poll cycle exception doesn't crash daemon

## Acceptance Criteria

- [ ] State machine rejects all invalid transitions with clear messages
- [ ] `iw daemon start --foreground` starts and polls (ctrl-C to stop)
- [ ] SIGHUP reloads projects.toml
- [ ] Startup health check detects dead PIDs and marks them failed
- [ ] One project's error doesn't block other projects
- [ ] `make test` passes, `make quality` passes
