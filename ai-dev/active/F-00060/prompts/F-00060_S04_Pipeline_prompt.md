# F-00060_S04_Pipeline_prompt

**Work Item**: F-00060 — Hybrid Code Q&A retrieval
**Step**: S04 — Daemon poller
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

Same rules as S01.

---

## Input Files

- `ai-dev/active/F-00060/F-00060_Feature_Design.md` — see *Scope*, *AC6*, *Invariants 5–6*
- `ai-dev/active/F-00060/reports/F-00060_S02_Backend_report.md` — `DocIndexJobRunner` API
- `orch/daemon/doc_job_poller.py` — the `DocJobPoller` pattern to mirror
- `orch/daemon/main.py` — daemon entry point / poll loop wiring

## Output Files

- `ai-dev/active/F-00060/reports/F-00060_S04_Pipeline_report.md` (new)
- `orch/daemon/doc_index_poller.py` (new)
- `orch/daemon/main.py` (modified — register the new poller)

## Context

S02 built the `DocIndexJobRunner`. This step adds the daemon poller that
picks up queued `doc_index_jobs` rows and launches runners, plus the
orphan-recovery guarantee on daemon boot.

## Requirements

### 1. `DocIndexPoller` — `orch/daemon/doc_index_poller.py`

Mirror `DocJobPoller` (see `orch/daemon/doc_job_poller.py`):

- Class attribute `MAX_CONCURRENT_JOBS_PER_PROJECT = 1` (docs are heavier
  than doc generation; serialise per project).
- `STALL_TIMEOUT_SECONDS = 600` (10 min).
- `poll(self) -> None`:
  1. Mark stalled jobs: any `status='running'` with
     `started_at < now() - STALL_TIMEOUT_SECONDS` → `status='failed'` with
     `error_message='stalled (exceeded 10 min)'`.
  2. For each enabled project: if `running_count < MAX_CONCURRENT_JOBS_PER_PROJECT`,
     dequeue the next `queued` job (oldest first) and launch a runner.
- Launch path: instantiate `DocIndexJobRunner`, register it in
  `JOB_REGISTRY_DOC`, and spawn `asyncio.create_task(runner.run())`.
- Respect `JobAlreadyRunningError` defensively (log + skip) in case of
  races with the registry.

### 2. Orphan recovery on daemon boot

Before the first `poll()` runs, execute a one-shot sweep:

```sql
UPDATE doc_index_jobs
SET status = 'failed',
    error_message = 'orphaned by daemon restart',
    completed_at = NOW()
WHERE status = 'running';
```

Inside Python, do this via the ORM with a single transaction. This MUST run
before any other doc-index-job logic so the registry does not collide with
a stale `running` row (Invariant 6).

Name the function `recover_orphaned_doc_index_jobs(session_factory)` and
export it so the daemon entry point can call it on startup.

### 3. Wire into `orch/daemon/main.py`

- Import `DocIndexPoller` and `recover_orphaned_doc_index_jobs`.
- In the daemon startup path (before the main poll loop begins), call
  `recover_orphaned_doc_index_jobs(SessionLocal)`.
- Instantiate one `DocIndexPoller` and call its `.poll()` each tick
  alongside the existing pollers. Preserve existing pollers' order;
  document the ordering choice in the report.

### 4. Do not change behaviour for other pollers

`DocJobPoller`, batch manager, merge queue, code-index poller (if any —
investigate whether `code_index_jobs` has its own poller and note findings
in the report) must remain byte-for-byte unchanged. If the code-index
pipeline has its own poller shape, this feature's poller follows the
same design contract.

## Project Conventions

Read `orch/CLAUDE.md`. Single-threaded polling loop; no background threads.
Sessions closed inside each `poll()` call (no long-lived sessions).

## TDD Requirement

1. **RED**:
   - `tests/integration/test_doc_index_poller.py`:
     - Insert a queued job → poll picks it up → runner launches → status
       transitions to running.
     - Two queued jobs for same project → only one runs (concurrency cap).
     - Running job exceeding stall timeout → marked failed with
       `stalled` message.
   - `tests/integration/test_doc_index_orphan_recovery.py`:
     - Pre-seed a running job → call `recover_orphaned_doc_index_jobs` →
       status = failed with `orphaned by daemon restart`.
     - Call the recovery twice in a row → idempotent; second call changes
       nothing.
2. **GREEN**: implement.
3. **REFACTOR**: verify the daemon still starts cleanly in a local dry-run
   (no DB writes outside the recovery function).

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — pass.
2. `make test-unit` — pass.
3. `make lint` + `make typecheck` — pass.

## Subagent Result Contract

Standard JSON with `step: "S04"`, `agent: "pipeline-impl"`, `work_item: "F-00060"`.
