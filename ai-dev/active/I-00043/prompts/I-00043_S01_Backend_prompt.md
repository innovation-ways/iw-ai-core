# I-00043_S01_Backend_prompt

**Work Item**: I-00043 — doc_index_poller crashes with DetachedInstanceError on every poll cycle
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers spun up by pytest fixtures, read-only `docker ps | inspect | logs`,
and invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT add or modify any migration. You MUST NOT run
`alembic upgrade/downgrade/stamp`.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00043/I-00043_Issue_Design.md` — Design document (read first; the "Root Cause Analysis" section has the fix)
- `orch/daemon/doc_index_poller.py` — File to fix (lines 44–55 are the affected `poll()` method)
- `orch/daemon/doc_job_poller.py` — Sibling poller; audit for the same pattern
- `orch/db/models.py` — `Project` model definition (for the `Project.id` column type)
- `orch/db/session.py` — Session factory; understand how `with self._session_factory() as db:` closes the session

## Output Files

- `orch/daemon/doc_index_poller.py` — Modified to materialise project IDs inside the session
- `orch/daemon/doc_job_poller.py` — Modified IF the same pattern exists; otherwise unchanged
- `ai-dev/active/I-00043/reports/I-00043_S01_Backend_report.md` — Step report with adjacent-poller audit findings

## Context

The current `poll()` in `orch/daemon/doc_index_poller.py:44-55` is:

```python
def poll(self) -> None:
    self._mark_stalled_jobs()

    with self._session_factory() as db:
        projects = db.query(Project).filter(Project.enabled == True).all()  # noqa: E712

    for project in projects:
        self._process_project(project.id)
```

The session closes at the end of the `with` block. The next line accesses
`project.id` on detached instances, which triggers an expired-attribute reload
that fails with `sqlalchemy.orm.exc.DetachedInstanceError`. The daemon catches
the exception and continues, so this fires every poll cycle (~60s) and has been
ignored.

Your job is to fix the lifecycle bug and audit the sibling poller.

## Requirements

### 1. Fix `DocIndexPoller.poll()`

Move the access of `project.id` inside the `with` block. Two acceptable forms:

**Form A — column-only query (preferred, smaller fetch):**

```python
def poll(self) -> None:
    self._mark_stalled_jobs()

    with self._session_factory() as db:
        project_ids = [
            pid for (pid,) in db.query(Project.id).filter(Project.enabled == True).all()  # noqa: E712
        ]

    for project_id in project_ids:
        self._process_project(project_id)
```

**Form B — ORM query with id extraction inside session:**

```python
def poll(self) -> None:
    self._mark_stalled_jobs()

    with self._session_factory() as db:
        project_ids = [
            p.id for p in db.query(Project).filter(Project.enabled == True).all()  # noqa: E712
        ]

    for project_id in project_ids:
        self._process_project(project_id)
```

Pick Form A. It's marginally more efficient (only the `id` column is fetched) and
makes the lifecycle correctness obvious — there is no ORM instance to get detached.

Do NOT introduce any new helpers, new methods, or refactor `_process_project`. The
fix is local to the four lines of `poll()` shown above.

### 2. Audit `orch/daemon/doc_job_poller.py` for the same pattern

Read `orch/daemon/doc_job_poller.py` end-to-end. Look for any `with self._session_factory() as db:`
block that returns ORM instances followed by attribute access outside the block.
There are two possible outcomes:

- **Same bug present**: apply the same fix (extract IDs inside the session).
- **Already correct**: confirm in writing in your step report. Quote the relevant
  lines and explain why the pattern is safe (e.g., "lines X–Y extract `job.id` and
  `job.project_id` inside the with block before closing the session").

Either way, report the audit result explicitly. Do NOT silently leave it unverified.

### 3. Do NOT touch any other files

Do NOT modify `_process_project`, `_mark_stalled_jobs`, the `Project` model,
`session.py`, the daemon main loop, or the executor scripts. Scope is the two
poller files only.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for project-specific patterns. Most
relevantly:

- The daemon is sync SQLAlchemy 2.0 — no `await`, no async sessions.
- The session factory closes the session on `__exit__`. Detached instances must
  not be accessed afterwards.
- Type annotations: PEP 604 (`X | Y`).
- The `# noqa: E712` comment on `Project.enabled == True` is required by ruff
  because SQLAlchemy needs the explicit `== True` for column comparisons. Keep it.

## TDD Requirement

The reproduction and regression tests are S03's deliverable. For your step:

1. **RED phase verification**: before applying your fix, run the daemon (or just
   `python -c "from orch.daemon.doc_index_poller import DocIndexPoller; ...; p.poll()"`)
   against a populated test DB and confirm the DetachedInstanceError fires. You can
   skip this if the bug is already documented in the daemon log — the design doc
   provides plenty of evidence.
2. **GREEN phase verification**: after your fix, run the same reproduction and
   confirm no error. The full check is in S03's test, but a quick smoke check
   here saves a fix-cycle round-trip.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make lint` — must pass.
2. `make typecheck` — must pass.
3. `make test-unit` — must pass with zero failures.

Do **NOT** report `tests_passed: true` unless all three pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00043",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/doc_index_poller.py"
  ],
  "tests_passed": true,
  "test_summary": "lint clean; typecheck clean; X unit passed, 0 failed",
  "blockers": [],
  "notes": "Audit of doc_job_poller.py: <ALREADY-CORRECT | FIXED-AS-WELL>; <quote of relevant lines and explanation>"
}
```

The `notes` field MUST include the explicit doc_job_poller.py audit result. If
`doc_job_poller.py` is in `files_changed`, the notes describe the fix applied;
if it is not, the notes prove (with line citations) that the file is already
correct.
