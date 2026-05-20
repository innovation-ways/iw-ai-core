# CR-00064_S01_API_prompt

**Work Item**: CR-00064 — Clear Chat History Button in AI Assistant
**Step**: S01
**Agent**: api-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step makes NO database schema or migration changes. The `opencode_session_id` column already exists.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00064 --json`
- `ai-dev/active/CR-00064/CR-00064_CR_Design.md` — Design document
- `dashboard/routers/chat.py` — Primary file to modify
- `orch/chat/opencode/client.py` — OpenCode `create_session` API
- `orch/chat/pi/pi_runtime.py` — Pi `create_session` API
- `orch/chat/tab_service.py` — `update_tab` service method
- `tests/dashboard/test_chat_router.py` — Existing tests (add new cases here)

## Output Files

- `ai-dev/active/CR-00064/reports/CR-00064_S01_API_report.md` — Step report

## Context

You are adding `POST /api/chat/tabs/{tab_id}/clear` to `dashboard/routers/chat.py`. This endpoint resets the LLM context for a chat tab by: creating a new session in the tab's runtime (OpenCode or Pi), updating the tab's `opencode_session_id` to the new session ID, and returning the updated tab dict.

## Requirements

### 1. New endpoint: `POST /api/chat/tabs/{tab_id}/clear`

Add a new route to `dashboard/routers/chat.py`. The endpoint must:

**Path**: `POST /api/chat/tabs/{tab_id}/clear`

**No request body** — all context is resolved from the tab row.

**Logic**:

1. Look up the tab: `tab = _tab_service.get_tab(db, tab_id)`. If `None`, return `JSONResponse(status_code=404, content={"error": "tab not found"})`.

2. If `tab.opencode_session_id` is `None` or empty, return `JSONResponse(status_code=400, content={"error": "tab has no session to clear"})`.

3. Store the old session ID: `old_sid = tab.opencode_session_id`.

4. **Pi runtime path** (`tab.runtime == "pi"`):
   - Get `pi_runtime = getattr(request.app.state, "pi_runtime", None)`. If `None`, return 503.
   - Check health: `await pi_runtime.health()`. If unhealthy, return 503.
   - Resolve `project_directory` from the project's Pi config (follow the same pattern used in `create_tab` around line 387 — look up `pi_config.get("project_directory")`).
   - Create new session: `new_sid = await pi_runtime.create_session(model=tab.model, directory=project_directory or None)`.
   - On exception: return `JSONResponse(status_code=503, content={"error": "Pi runtime unavailable"})`.

5. **OpenCode path** (default):
   - Check `healthy` via `Depends(_check_runtime_healthy)`. If not healthy or `client is None`, return `_503_unavailable()`.
   - Resolve `project_directory` from the project's OpenCode config (follow the pattern used in `create_tab` for the OpenCode branch around line 495 — look up `project_directory` from `_config_cache` or fetch from client).
   - Create new session: `new_sid = await client.create_session(model=tab.model, directory=project_directory or None)`.
   - On exception: return `JSONResponse(status_code=503, content={"error": "OpenCode runtime unavailable"})`.

6. **Close old relay** (if a relay manager exists):
   - `relay_manager = _get_relay_manager(request)` (use the existing `_get_relay_manager` helper already in `chat.py`).
   - If `relay_manager` is not None, call `await relay_manager.drop_relay(tab_id)` to stop the pump for the old session before creating the new one. (`drop_relay(tab_id: str)` is defined in `orch/chat/opencode/relay_manager.py` — it stops the relay and removes it from the manager's dict.)

7. **Update the tab**:
   ```python
   tab = _tab_service.update_tab(db, tab_id, opencode_session_id=new_sid)
   db.commit()
   ```
   Check if `_tab_service.update_tab` accepts `opencode_session_id` as a parameter. If not, update the row directly:
   ```python
   tab.opencode_session_id = new_sid
   db.commit()
   db.refresh(tab)
   ```

8. **Return**: `{"tab": _tab_to_dict(tab)}` with status 200.

**Dependency injection**: Use the same `Depends(...)` pattern as `get_tab` and `prompt` endpoints:
- `request: Request`
- `client: OpencodeClient | None = Depends(_get_client)`
- `healthy: bool = Depends(_check_runtime_healthy)`
- `db: Session = Depends(get_db)`

### 2. Tests in `tests/dashboard/test_chat_router.py`

Add the following test cases (follow existing patterns in the file):

- `test_clear_tab_returns_updated_tab` — mock `create_session` to return a new UUID; assert response status 200 and new `opencode_session_id` in response.
- `test_clear_tab_not_found` — assert 404 for unknown tab ID.
- `test_clear_tab_no_session` — assert 400 when tab has no `opencode_session_id`.
- `test_clear_tab_runtime_unavailable` — mock runtime as unhealthy; assert 503.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Key rules:
- Routers are thin — delegate session creation to the runtime clients directly (no new service layer needed).
- Use `async def` for the route (all chat routes are async).
- Return `JSONResponse` for errors; plain `dict` (auto-serialized) for success is fine, but follow the pattern of `{"tab": _tab_to_dict(tab)}` as used in `get_tab`, `update_tab`, etc.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write the 4 test cases first. Run only those tests — confirm they fail with `AttributeError` or `AssertionError` (not import errors). Capture the failing output.
2. **GREEN**: Implement the endpoint. Re-run the 4 tests — all must pass.
3. **REFACTOR**: Check for duplication with `create_tab`; extract shared helpers only if the pattern is used 3+ times.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:
1. `make format`
2. `make typecheck` — zero errors on touched files
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_chat_router.py -v -k "clear" --no-header
```

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "api-impl",
  "work_item": "CR-00064",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/chat.py",
    "tests/dashboard/test_chat_router.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "4 passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_chat_router.py::test_clear_tab_returns_updated_tab — AttributeError: ...",
  "blockers": [],
  "notes": ""
}
```
