# F-00092_S06_Pipeline_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S06
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

No persistent container/volume changes. The poller calls the S03 engine, which may
`docker run --rm` for pg client tools. Do not run against the live 5433 DB in dev.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this step.

## Input Files

- `uv run iw item-status F-00092 --json`.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md` — **Scope**, **Invariant 4**,
  AC1, AC4 (catch-up), Boundary rows (disabled / recent-success / DB-unreachable).
- `orch/daemon/doc_job_poller.py`, `orch/daemon/chat_summarization_poller.py`,
  `orch/daemon/doc_index_poller.py` — existing poller patterns.
- `orch/daemon/main.py` — how pollers are constructed and invoked in the loop
  (around lines 219, 345, 588).
- S03/S05 reports — engine + prune signatures.

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S06_Pipeline_report.md`.

## Context

Add the daemon component that runs scheduled backups daily with missed-window
catch-up, and triggers retention pruning. Follow the existing poller pattern.

## Requirements

### 1. Backup poller (`orch/daemon/backup_poller.py`)

- On each poll cycle, decide whether a **scheduled** backup is due:
  - If `IW_CORE_BACKUP_ENABLED` is false → do nothing.
  - Determine the daily window from `IW_CORE_BACKUP_TIME`.
  - **Due** if there is no successful *scheduled* `DbBackupJob` within the current
    interval AND the window time has passed (this gives **catch-up**: a backup runs
    as soon as the daemon recovers from being down across the window — AC4).
  - If a recent successful scheduled backup exists within the interval → do nothing
    (Boundary "recent success").
- When due, call the S03 engine with `backup_type=scheduled`, then invoke the S05
  retention prune.
- Robust failure handling: a failed backup is recorded `failed` (not `success`), so
  the next poll still treats the window as unsatisfied and retries (Boundary
  "DB unreachable"). Do not crash the daemon loop on backup failure — log and
  continue, matching the other pollers' resilience.
- Pure scheduling decisions (due / not due / catch-up) should be factored so they
  are unit-testable with an injected "now" and a stubbed last-success timestamp.

### 2. Wire into `orch/daemon/main.py`

Construct and invoke the poller in the daemon loop alongside the existing pollers
(mirror how `doc_job_poller` / `chat_summarization` are wired). Respect the existing
poll cadence; do not add a tight loop.

Do NOT implement the CLI, Jobs UI, or docs here.

## Project Conventions

Read `CLAUDE.md` (daemon design) and match the existing poller structure, logging,
and session handling exactly.

## TDD Requirement (RED first)

Write failing unit tests for the due/catch-up decision logic first (recent-success
→ not due; missed-window → due; disabled → never due), with injected now + last
success, capture RED, then implement.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — zero new errors.

## Test Verification (NON-NEGOTIABLE)

Targeted unit tests only.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "pipeline-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "files_changed": ["orch/daemon/backup_poller.py", "orch/daemon/main.py", "tests/unit/..."],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (targeted)",
  "tdd_red_evidence": "tests/unit/.../test_backup_poller.py::test_catch_up_when_missed — AssertionError ... // RED",
  "blockers": [],
  "notes": "Document where in the loop the poller runs."
}
```
