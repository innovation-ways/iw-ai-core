# F-00063 S03 — API Step Report

**Work item**: F-00063 — Stale Process & Migration Detector
**Step**: S03 (api-impl)
**Status**: complete

## Summary

Implemented the FastAPI router exposing the staleness backend over HTTP. All endpoints, the 5-second per-service in-memory soft-lock, the detached self-restart pathway for the dashboard, and the alembic-upgrade endpoint with env-var injection are in place. Tests are TDD-first (RED-before-GREEN).

## Files Touched

### New
- `dashboard/routers/staleness.py` — six endpoints (GET panel, GET dot, POST restart/start/stop per service, POST alembic upgrade) + 5-second soft-lock dict + helpers (`_load_projects_toml`, `_get_service_config`, `_get_alembic_config`, `_get_repo_root`, `_toast_response`).
- `tests/dashboard/test_staleness_router.py` — integration tests using FastAPI TestClient. Covers: panel happy path, opt-out empty body, unknown project 404, restart subprocess invocation, 5s soft-lock 429 with `Retry-After`, missing restart command 409, alembic upgrade happy/fail (502).

### Modified
- `dashboard/app.py` — imported `staleness` and added `app.include_router(staleness.router)` next to other routers.

## Endpoint Behavior

| Endpoint | Success | Errors |
|----------|---------|--------|
| `GET /projects/{id}/staleness` | 200 panel HTML | 200 empty body for opt-out, 404 unknown |
| `GET /projects/{id}/staleness-dot` | 200 dot HTML or empty | 404 unknown |
| `POST /projects/{id}/services/{name}/restart` | 204 (or 202 self-restart) + `HX-Trigger` toast | 404 unknown, 409 no command, 429 soft-lock |
| `POST /projects/{id}/services/{name}/start` | 204 + toast | 404, 409, 429 |
| `POST /projects/{id}/services/{name}/stop` | 204 + toast | 404, 409, 429 |
| `POST /projects/{id}/alembic/upgrade` | 200 + alembic stdout in toast | 404 no alembic block, 502 alembic failure |

## Verification

| Gate | Command | Result |
|------|---------|--------|
| Lint | `make lint` | exit 0 |
| Typecheck | `make typecheck` | exit 0 (190 source files) |
| Unit tests | `make test-unit` | 1844 passed, 2 skipped |
| Staleness router tests | `uv run pytest tests/dashboard/test_staleness_router.py -v` | passed |

## Notes

- **Soft-lock**: module-level `dict[tuple[str, str], float]`. Single uvicorn worker assumption documented in module docstring.
- **shell=True intentional**: `restart_command`/`start_command`/`stop_command` are operator-supplied strings from `projects.toml` that may contain shell features (pipes, `&&`, env expansion). Documented in module docstring with the trust boundary explanation.
- **Self-restart**: dashboard `restart_command` (`bin/restart-dashboard.sh`) is spawned with `start_new_session=True` and the endpoint returns 202 immediately so the HTTP response flushes before the helper kills the dashboard.
- **Alembic env injection**: when `db_url_env` is configured, its value is propagated into the subprocess (and exposed as `IW_ALEMBIC_DB_URL` for env.py files that look for it). When omitted, the subprocess inherits the parent environment unchanged — matches `check_alembic`'s contract from S01.
- **Lint cleanups during the pass**: removed four `# POST /projects/...` section header comments that ruff flagged as ERA001 commented-out code. Replaced with plain prose section headers.
- **Mypy cleanups**: added explicit `cast()` calls to three helper return paths where TOML data dict unpacking lost type information.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "api-impl",
  "work_item": "F-00063",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/routers/staleness.py",
    "dashboard/app.py",
    "tests/dashboard/test_staleness_router.py"
  ],
  "tests_passed": true,
  "test_summary": "All staleness router tests + full unit suite (1844 passed, 2 skipped) green; lint and typecheck clean.",
  "blockers": [],
  "notes": "Templates referenced (staleness_panel.html, staleness_dot.html, staleness_confirm.html) are owned by S04; both deliverables present in repo."
}
```
