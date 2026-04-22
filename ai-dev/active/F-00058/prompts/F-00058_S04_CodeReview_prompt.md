# F-00058_S04_CodeReview_prompt

**Work Item**: F-00058
**Step Being Reviewed**: S03 (backend-impl — oss_service)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (2026-04-22 incident).

Allowed:
  1. Testcontainers spun up by pytest fixtures (they self-destruct via Ryuk).
  2. Read-only introspection: docker ps | inspect | logs.
  3. Invocations through ./ai-core.sh or make targets.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule. If a testcontainer appears
stuck, rely on pytest teardown / Ryuk — never `docker kill` it.

---

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md`
- `ai-dev/active/F-00058/reports/F-00058_S03_Backend_report.md`
- Files listed in S03 report

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S04_CodeReview_report.md`

## Review Checklist

### 1. Architecture Compliance
- No direct DB writes outside ORM; routers cannot import session directly from service internals.
- Service does NOT import from `dashboard/routers/*`.
- Throwaway worktree logic uses real `git worktree add/remove`; no shell=True.

### 2. Subprocess hygiene
- `asyncio.create_subprocess_exec` everywhere; no `subprocess.run`.
- stdout/stderr bounded (16KB tail); no unbounded in-memory buffers.
- Subprocess timeout enforced per operation (scan vs prepare vs publish — different limits OK).
- Cancellation (task cancel or explicit `cancel_job`) cleanly terminates child + cleans worktree.

### 3. Worktree lifecycle
- Cleanup runs on every exit path (success, error, cancel, exception mid-execute).
- Orphan recovery on service startup: jobs in `running` status older than process start → `error` with clear message; matching `/tmp/oss-*` dirs removed.
- Worktree paths are absolute and unique (uuid-based), not user-influenced.

### 4. SSE
- Heartbeat every ~20s to avoid proxy timeouts.
- Replay-on-reconnect returns current `stdout_tail` as `progress` events before live updates.
- Message format is valid SSE (`event: X\ndata: Y\n\n`).
- Backpressure: if client slow, server doesn't OOM.

### 5. State transitions
- Monotonic: `queued → running → {complete|error|cancelled}`; no regressions (invariant #2).
- `completed_at` set exactly once.

### 6. Testing
- Integration tests cover: enqueue, execute, cancel, orphan recovery, SSE replay.
- Unit tests for SSE formatter + freshness helper.
- Testcontainer Postgres (CLAUDE.md).

### 7. Security
- No shell=True.
- Absolute paths only for subprocess args.
- Project slug validated against known projects (no directory traversal).

## Test Verification (NON-NEGOTIABLE)

`make test-unit` + `make test-integration` + `make lint` + `uv run mypy dashboard/services/` pass.

## Review Result Contract

Standard JSON. `verdict: pass` only when zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
