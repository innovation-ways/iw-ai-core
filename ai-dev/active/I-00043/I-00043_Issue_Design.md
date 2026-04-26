# I-00043: doc_index_poller crashes with DetachedInstanceError on every poll cycle

**Type**: Issue
**Severity**: High
**Created**: 2026-04-26
**Reported By**: Operator (sergio) — observed in daemon logs after CR-00022 merge
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state
(`docker kill | stop | rm | restart | compose up/down/restart | volume rm | system prune`).

Allowed exceptions: testcontainers spun up by pytest fixtures, read-only introspection
(`docker ps | inspect | logs`), and invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This issue does NOT add or modify any migration. It is a pure code fix in the
daemon poller.

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orchestration DB.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Description

The daemon's `DocIndexPoller.poll()` queries the `Project` table inside a SQLAlchemy
session, then iterates the results **after** the session has closed. Accessing
`project.id` on the detached instances triggers an expired-attribute load that fails
with `sqlalchemy.orm.exc.DetachedInstanceError`. The error is caught at the daemon
poll-cycle boundary and logged, so the daemon stays alive — but `_process_project`
is never called, doc indexing for every project is silently halted, and the error
fires once per poll cycle (~60s). The daemon log has accumulated ~3,000 occurrences
since 2026-04-24.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Most
relevantly:

- `orch/daemon/doc_index_poller.py` is the affected file. Its `poll()` method
  follows the daemon's "fetch-in-session, work-after-session" pattern but does so
  incorrectly — it returns ORM instances from the session and accesses their
  attributes outside the `with` block.
- `orch/daemon/doc_job_poller.py` is a sibling poller (DocGenerationJob queue) and
  is a useful comparison: confirm during S01 whether it has the same bug or
  whether it correctly extracts plain IDs before closing the session.
- `orch/db/session.py` exports `SessionLocal` / `get_session()`. The session
  context manager closes the session on exit, expiring all attached instances.
- The daemon main loop in `orch/daemon/main.py:_poll_cycle` wraps each poller
  call in a try/except (`Error in doc index poller — continuing`), which is
  why the daemon stays alive despite this exception firing every cycle.

## Steps to Reproduce

1. Have at least one enabled `Project` row in the live orch DB (the `iw-ai-core`,
   `innoforge`, and `cv` projects all qualify).
2. Restart the daemon (`./ai-core.sh daemon restart`).
3. Tail `logs/daemon.log` for the next 2 minutes.
4. Observe entries of the form (one per poll cycle):
   ```
   ERROR    orch.daemon.main: Error in doc index poller — continuing
   Traceback (most recent call last):
     File ".../orch/daemon/main.py", line 490, in _poll_cycle
       self.doc_index_poller.poll()
     File ".../orch/daemon/doc_index_poller.py", line 55, in poll
       self._process_project(project.id)
                             ^^^^^^^^^^
     ...
   sqlalchemy.orm.exc.DetachedInstanceError: Instance <Project at 0x...> is not
   bound to a Session; attribute refresh operation cannot proceed
   ```

**Expected**: `DocIndexPoller.poll()` calls `_process_project(project_id)` once for
every enabled project, with no DetachedInstanceError. Doc index jobs are dequeued
and launched.

**Actual**: The first iteration of the for-loop raises DetachedInstanceError on
`project.id`, the entire poll cycle is aborted, and no `_process_project` calls
ever happen.

## Root Cause Analysis

`orch/daemon/doc_index_poller.py:51-55` is:

```python
with self._session_factory() as db:
    projects = db.query(Project).filter(Project.enabled == True).all()  # noqa: E712

for project in projects:
    self._process_project(project.id)
```

When the `with` block exits, `db.close()` runs, which expires every ORM instance
attached to the session. The `projects` list now contains detached instances. On
the next line, `project.id` triggers SQLAlchemy's expired-attribute loader, which
needs a session to refresh from — there isn't one — so it raises
`DetachedInstanceError`.

The fix is to materialise plain Python values for `project.id` **inside** the
session, before the session closes:

```python
with self._session_factory() as db:
    project_ids = [
        pid for (pid,) in db.query(Project.id).filter(Project.enabled == True).all()  # noqa: E712
    ]

for project_id in project_ids:
    self._process_project(project_id)
```

Selecting only the `id` column avoids fetching unneeded columns and produces plain
strings that survive session close. Equivalent acceptable form:
`project_ids = [p.id for p in db.query(Project).filter(...).all()]` evaluated
inside the `with` block — that also reads `id` while the session is still open.

The bug exists only in `poll()`. `_process_project` already takes a `project_id: str`
and opens its own session for the work it does, so it is correct as-is. No other
file needs to change.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/doc_index_poller.py:51-55` | Every poll cycle raises DetachedInstanceError; `_process_project` is never invoked |
| `DocIndexJob` queue | Queued jobs are never picked up by the daemon — code-indexing is effectively offline |
| `logs/daemon.log` | Accumulates one full traceback per minute; ~3,000 occurrences over 2 days |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Materialise `project_id` strings inside the session in `DocIndexPoller.poll()`; check `doc_job_poller.py` for the same pattern and fix it if present | — |
| S02 | CodeReview | Review S01 fix and adjacent-poller audit | — |
| S03 | Tests | Reproduction unit test (poll() against fake session factory; verify `_process_project` is invoked once per project; verify no DetachedInstanceError) | — |
| S04 | CodeReview | Review S03 tests for semantic correctness and falsifiability | — |
| S05 | CodeReview_Final | Global review across S01 + S03 | — |
| S06 | QV gate | lint | — |
| S07 | QV gate | format | — |
| S08 | QV gate | typecheck | — |
| S09 | QV gate | unit-tests | — |
| S10 | QV gate | integration-tests | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A — no migration in this incident.

### Code Changes

- **Files to modify**:
  - `orch/daemon/doc_index_poller.py` — fix `poll()` to extract project IDs inside the session.
  - `orch/daemon/doc_job_poller.py` — only if the same pattern exists; S01 audits this and either fixes or documents it as already-correct.
- **Nature of change**: Move the `project.id` access inside the `with self._session_factory() as db:` block.

## File Manifest

All files for this work item live under `ai-dev/active/I-00043/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00043_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00043_S01_Backend_prompt.md` | Prompt | S01 fix instructions |
| `prompts/I-00043_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review of fix |
| `prompts/I-00043_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00043_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of tests |
| `prompts/I-00043_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |

Source files modified:

| File | Type | Purpose |
|------|------|---------|
| `orch/daemon/doc_index_poller.py` | Modified | Fix session-boundary bug |
| `orch/daemon/doc_job_poller.py` | Modified (conditional) | Same fix if same pattern present |
| `tests/unit/daemon/test_doc_index_poller_session_boundary.py` | New test | Reproduction + regression |

## Test to Reproduce

The reproduction test must demonstrate that `poll()` invokes `_process_project`
once per enabled project without raising DetachedInstanceError.

```python
# tests/unit/daemon/test_doc_index_poller_session_boundary.py

from unittest.mock import MagicMock
from orch.daemon.doc_index_poller import DocIndexPoller


def test_poll_does_not_raise_detached_instance_error_for_each_project(...):
    """RED before I-00043: project.id is accessed after the session closes,
    raising DetachedInstanceError. GREEN after the fix: poll() invokes
    _process_project(project_id) once for each enabled project, no exception.
    """
    # Arrange: a real testcontainer-backed session factory with two enabled
    # projects seeded; spy on _process_project.
    poller = DocIndexPoller(session_factory=..., config=...)
    seen: list[str] = []
    poller._process_project = lambda pid: seen.append(pid)

    # Act
    poller.poll()

    # Assert
    assert seen == ["project_a", "project_b"], (
        f"Expected _process_project to be called for both enabled projects "
        f"in order, got {seen}"
    )
```

The test must run against a real testcontainer-backed session factory (not a
mocked session), because the bug is a real-session lifecycle issue. A mocked
session that returns plain attribute values would never trigger
DetachedInstanceError and the test would silently pass against the bug.

## Acceptance Criteria

### AC1: Bug is fixed

```
Given the live orch DB has at least one enabled Project
When DocIndexPoller.poll() is invoked
Then _process_project is called once with each enabled project's id
And no DetachedInstanceError is raised
And no entry containing "Error in doc index poller" is written to the daemon log
```

### AC2: Regression test exists

```
Given the fix is applied
When `make test-unit` runs (or the new test file is run directly)
Then test_poll_does_not_raise_detached_instance_error_for_each_project passes
And the test would fail if the fix in poll() were reverted
```

### AC3: Adjacent poller audit

```
Given the fix is in place for DocIndexPoller
When I read orch/daemon/doc_job_poller.py
Then either the same session-boundary fix is applied there too
Or the S01 report explains in writing why doc_job_poller is unaffected
(e.g., quoting the line that already extracts ids before closing)
```

## Regression Prevention

The regression test exercises a real session, so any future change that returns
attached ORM instances across a session boundary will fail it.

For broader prevention, consider a follow-up CR that wraps every "fetch projects
inside session" pattern in the daemon (`batch_manager`, `merge_queue`,
`step_monitor`, etc.) in a single helper that always returns plain `project_id`
strings. Out of scope for this incident.

## Dependencies

- **Depends on**: None.
- **Blocks**: None. The bug has been silent for 2 days; doc indexing has been
  offline for that period but no other functionality has degraded.

## TDD Approach

- **Reproducing test**: `test_poll_does_not_raise_detached_instance_error_for_each_project`
  — fails on pre-fix code, passes after the fix. Uses a real testcontainer session
  factory (not mocks) so the lifecycle bug actually triggers.
- **Unit tests**: The reproduction test is the unit test; no further unit coverage
  needed.
- **Integration tests**: None needed — this is a pure poller-layer bug; the
  existing daemon integration tests already exercise full poll cycles and will
  catch any regression.

## Notes

- The bug is silent: the daemon catches the exception and continues, so there is
  no user-visible alert. The only signal was the operator noticing the log volume.
- After the fix, the existing daemon log will still show the old errors (one per
  poll cycle for the past 2 days) — those are historical and do NOT need
  cleanup. New errors will stop appearing once the daemon is restarted with the
  fix.
- The same lifecycle pitfall exists generally throughout the SQLAlchemy ORM. The
  short-term fix is local; the long-term prevention is the audit + helper
  proposed above.
