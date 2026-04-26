# F-00063_S05_CodeReview_API_prompt

**Work Item**: F-00063 -- Stale Process & Migration Detector
**Step Being Reviewed**: S03 (api-impl)
**Review Step**: S05

---

## ⛔ Docker is off-limits

You MUST NOT execute docker container/volume/network mutating commands. Read-only commands and testcontainers in fixtures are allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live orch DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00063/F-00063_Feature_Design.md`
- `ai-dev/active/F-00063/reports/F-00063_S03_API_report.md`
- All files listed in S03's `files_changed`

## Output Files

- `ai-dev/active/F-00063/reports/F-00063_S05_CodeReview_report.md`

## Context

You are reviewing the staleness API endpoints (S03): `dashboard/routers/staleness.py`, the `dashboard/main.py` registration, and the integration tests.

## Review Checklist

### 1. Endpoint correctness

- All seven endpoints present (panel GET, dot GET, three service action POSTs, alembic upgrade POST).
- 404 for unknown project / service.
- 409 when the configured command is missing for that action.
- 429 with `Retry-After` for the soft-lock.
- 502 for alembic-upgrade subprocess failure.
- 200/204 with `HX-Trigger` toast on success.
- Self-restart endpoint returns 202 (not 204) and spawns detached.

### 2. Subprocess invocation safety

- Every `Popen`/`run` has an explicit timeout where applicable.
- `start_new_session=True` for restart actions so they survive the FastAPI worker.
- `cwd=<project_repo_root>` set explicitly.
- `shell=True` is documented as intentional (operator-trusted config strings) and never invoked with attacker-controlled input.
- Alembic upgrade has a hard timeout (60s) and captures stdout/stderr for the response.

### 3. Soft-lock behavior

- The 5s window is per `(project_id, service_name)` — not global.
- Lock state lives in module-level memory and is reset by process restart (acceptable; commented).
- Concurrent requests within the window all return 429.

### 4. Project conventions

- Style matches `dashboard/routers/daemon_control.py`.
- Uses existing toast trigger helper (don't invent a new one).
- Router registered in `dashboard/main.py` next to siblings.
- ruff and mypy clean.

### 5. Security

- Project / service name validated against the loaded config — no path traversal.
- `db_url_env` value never logged.
- No additional secrets introduced.

### 6. Testing

- Integration tests cover: panel happy path; opt-out empty body; 404; restart success; 429; 409; alembic happy + failure.
- Tests mock `Popen` and the `compute_project_staleness` orchestrator — no live subprocesses.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make lint`
3. `make typecheck`

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE → block merge. MEDIUM_SUGGESTION / LOW informational.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "F-00063",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
