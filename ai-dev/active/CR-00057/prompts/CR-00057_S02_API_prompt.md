# CR-00057_S02_API_prompt

**Work Item**: CR-00057 — AI Assistant chat model allowlist (per-project, with Ollama provider)
**Step**: S02
**Agent**: api-impl

---

## ⛔ Docker is off-limits

Standard policy (see template). This step does not touch containers.

## ⛔ Migrations: agents generate, daemon applies

This step does not add or modify any migration.

## Input Files

- `ai-dev/active/CR-00057/CR-00057_CR_Design.md` — design (read AC1, AC3, AC4 carefully)
- `ai-dev/active/CR-00057/reports/CR-00057_S01_Backend_report.md` — confirms the `Project.config["ai_assistant"]` shape is in place
- `dashboard/routers/chat.py` — file you are modifying (`get_config` at line 311; `_flatten_provider_models` and `_pick_default_model` helpers; `CreateSessionRequest` body model)
- `orch/db/models.py:Project` — for the JSONB `config` access pattern
- `dashboard/dependencies.py::get_db` — request-scoped DB session
- `CLAUDE.md`, `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00057/reports/CR-00057_S02_API_report.md`
- Modified: `dashboard/routers/chat.py`
- New tests in `tests/dashboard/test_chat_router.py` (extend the existing module, do NOT create a parallel file)

## Context

The chat panel's model dropdown is populated by `GET /api/chat/config`. Today the endpoint returns the full opencode provider flatten. You will add a `project_id` query parameter and, when supplied for a project that has `config["ai_assistant"]`, restrict the response to the intersection of the allowlist with what opencode actually reports.

## Requirements

### 1. Add `project_id` to `GET /api/chat/config`

Signature change in `dashboard/routers/chat.py`:

```python
@router.get("/config")
async def get_config(
    project_id: str | None = None,
    db: Session = Depends(get_db),
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
```

- When `project_id` is `None` or empty → preserve today's exact behavior (full flatten, today's default model logic). This is the **fail-open** branch.
- When `project_id` is supplied → look up the `Project` row via `db.get(Project, project_id)`. If not found, or its `config.get("ai_assistant")` is absent, log INFO (`"Chat config fallback: project=%s has no ai_assistant allowlist — returning full provider list"`) and return the fail-open list.
- Otherwise compute the intersection (see §2).

### 2. Allowlist intersection

After fetching `providers_raw` (and the existing `_flatten_provider_models(providers_raw)` result, call it `available_models`):

- Read `allowlist = project.config["ai_assistant"]["models"]` and `allow_default = project.config["ai_assistant"].get("default_model")`.
- `filtered = [m for m in allowlist if m in set(available_models)]` — preserves allowlist order, drops anything not reachable.
- If any entries were dropped, log a WARNING with the list of dropped entries (single line, comma-separated).
- If `filtered` is empty after the intersection, fall back to the fail-open list and log WARNING (don't return an empty dropdown — that's worse UX than the unfiltered list).
- Pick `default_model`:
  1. `allow_default` if it survived the filter,
  2. otherwise the first entry in `filtered`,
  3. otherwise (only when we hit the empty-filter fallback) today's `_pick_default_model` logic.

Return `{"models": filtered, "default_model": <picked>, "default_agent": raw.get("default_agent", "")}`.

### 3. Project-aware cache key

The current `_config_cache` is a single-key cache (`data` / `at`). Replace it with a dict keyed by `project_id or "__none__"`:

```python
_config_cache: dict[str, dict[str, Any]] = {}  # key: project_id or "__none__"; value: {"data": ..., "at": ...}
```

Preserve the 30 s TTL and the "serve stale on unhealthy runtime" behavior, per cache slot. Keep tests light — `_CONFIG_TTL` stays mutable for tests.

### 4. `directory` forwarding in session creation

`CreateSessionRequest` already has a `directory: str | None`. No schema change. Verify the existing `create_session` handler forwards it to `client.create_session(directory=body.directory)` — it already does at line 193. No code change here, but mention it in your report so the reviewer knows the wire was already in place; the frontend (S03) will start populating it.

### 5. Tests (extend `tests/dashboard/test_chat_router.py`)

Use the existing fixture style — `TestClient` against the FastAPI app with mocked `OpencodeClient`. Add:

- `test_get_config_no_project_id_returns_full_list` — confirms today's behavior on the un-keyed path.
- `test_get_config_with_project_id_filters_to_allowlist` — seed a `Project` row with a 3-entry allowlist; mock opencode to advertise 10 models including those 3 + 2 unreachable allowlist entries; assert response contains only the 3 reachable allowlist entries in allowlist order.
- `test_get_config_project_without_allowlist_falls_back` — Project row exists but no `ai_assistant` key in config → fail-open + INFO log.
- `test_get_config_unknown_project_id_falls_back` — `project_id` doesn't match any row → fail-open + INFO log.
- `test_get_config_filter_drops_unreachable_with_warning` — caplog at WARNING level captures the dropped entries.
- `test_get_config_default_model_preserved_when_in_filter` — `default_model` survives intersection → returned.
- `test_get_config_default_model_dropped_falls_to_first_filtered` — `default_model` was filtered out → first filtered entry returned.
- `test_get_config_empty_filter_falls_open_with_warning` — allowlist has zero overlap with available models → fail-open list returned + WARNING log.
- `test_get_config_cache_keyed_per_project` — two consecutive calls with different `project_id` values both populate the cache; mutating one doesn't poison the other.

Mock the opencode client at the `app.state` level (consistent with the existing tests).

### 6. Do not regress existing tests

```bash
uv run pytest tests/dashboard/test_chat_router.py -v
```

## TDD Requirement

RED-GREEN-REFACTOR. Capture the RED snippet for `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format` → `make typecheck` → `make lint`. Zero errors on files you touched.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "api-impl",
  "work_item": "CR-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/routers/chat.py", "tests/dashboard/test_chat_router.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_chat_router.py::test_get_config_with_project_id_filters_to_allowlist — TypeError: get_config() got an unexpected keyword argument 'project_id'",
  "blockers": [],
  "notes": ""
}
```
