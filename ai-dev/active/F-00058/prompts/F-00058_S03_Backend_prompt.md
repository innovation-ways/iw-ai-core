# F-00058_S03_Backend_prompt

**Work Item**: F-00058
**Step**: S03
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md`
- `ai-dev/active/F-00058/reports/F-00058_S01_Database_report.md` + S02 review verdict
- `orch/oss/` (from F-00057) — tool_probe, config_writer, scanner

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S03_Backend_report.md`
- `dashboard/services/__init__.py` (create if absent)
- `dashboard/services/oss_service.py` (new)

## Context

You build the dashboard-side service that orchestrates OSS compliance jobs on behalf of HTTP handlers. It enqueues `project_oss_job` rows, spawns `uv run iw oss …` subprocesses, provisions a throwaway worktree for prepare/publish, streams stdout to the DB, and exposes helpers for Tier-1 probe + freshness computation.

## Requirements

### 1. Job queue + executor

```python
async def enqueue_job(session, project, kind) -> ProjectOssJob: ...
async def run_job(session_factory, job_id: int) -> None: ...  # fire-and-forget worker
async def cancel_job(session, job_id: int) -> None: ...
```

- `run_job`:
  - Sets `status='running'`, `started_at=now()`.
  - For `kind='scan'`: runs `uv run iw oss scan --project {slug}` against the live working dir (read-only).
  - For `kind='prepare'`/`'publish'`: `git worktree add /tmp/oss-{uuid} HEAD` → cd into worktree → `uv run iw oss prepare|publish --project {slug}` → record worktree_path → cleanup `git worktree remove --force` on any exit.
  - Streams combined stdout/stderr; persists latest 16KB tail to `stdout_tail` every ~1s.
  - On completion: sets `status` to `complete`/`error`, `exit_code`, `completed_at`. If scan completed and F-00057 persisted an `oss_scan` row, store the scan_id FK.
- `cancel_job`: sends SIGTERM, waits, sends SIGKILL if needed; sets `status='cancelled'`; cleans worktree.

### 2. Server-shutdown safety

On service startup, mark any `status='running'` jobs older than the process start as `error` with `error_message='orphaned by server restart'` and clean up matching `/tmp/oss-*` worktrees. (Invariant #3.)

### 3. SSE message emission helpers

```python
async def job_event_stream(session_factory, job_id: int):
    """Yields SSE-formatted messages:
      - event: status, data: {status}
      - event: progress, data: {line}
      - event: complete, data: {exit_code, scan_id, pill_color}
    Includes 20s heartbeat.
    Supports replay: on first call returns current stdout_tail as 'progress' events,
    then subscribes to live updates.
    """
```

### 4. Wrappers around F-00057 services

```python
def probe_tier1(): ...              # delegates to orch.oss.tool_probe.probe_tier1
def compute_freshness(project): ... # compares latest oss_scan.head_sha vs `git rev-parse HEAD`
def latest_scan(session, project):  # returns latest OssScan row or None
def scan_summary(session, project): # returns the AC1 contract shape
```

## Project Conventions

- `dashboard/services/` mirrors `dashboard/routers/` one-to-one; keep routers thin.
- No direct ORM access in routers; use service functions.
- No raw SQL in services.
- Subprocess: `asyncio.create_subprocess_exec` only; no `subprocess.run`, no `shell=True`.

## TDD Requirement

Tests to add/drive:
- `tests/integration/test_oss_dashboard_service.py`:
  - enqueue → run_job → status transitions
  - cancellation terminates subprocess + cleans worktree
  - orphan recovery on startup
  - SSE stream replay + live update
- Unit:
  - SSE message formatter
  - freshness helper with mocked git output

## Test Verification (NON-NEGOTIABLE)

`make test-unit` + `make test-integration` + `make lint` + `uv run mypy dashboard/services/` pass.

## Subagent Result Contract

Standard JSON. `files_changed` lists services + tests.
