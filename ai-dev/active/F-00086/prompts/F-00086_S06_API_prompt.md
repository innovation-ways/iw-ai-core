# F-00086_S06_API_prompt

**Work Item**: F-00086 -- Multi-tab AI Assistant on OpenCode
**Step**: S06
**Agent**: api-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. You do not write or run migrations.)

## Input Files

- **Runtime step state** — `uv run iw item-status F-00086 --json`.
- `ai-dev/active/F-00086/F-00086_Feature_Design.md` — design document (read §API Changes, §Acceptance Criteria, §Boundary Behavior in full)
- `ai-dev/active/F-00086/reports/F-00086_S03_Backend_report.md` — S03 report (tab_service surface)
- `ai-dev/active/F-00086/reports/F-00086_S05_CodeReview_FIX_report.md` (if present) — S05 fix report
- Existing router: `dashboard/routers/chat.py` (611 lines, 9 endpoints) — you are rewriting this

## Output Files

- `dashboard/routers/chat.py` — rewritten to tab-scoped surface (11 endpoints)
- `dashboard/app.py` — `_lifespan` updated to construct the runtime + relay manager + (potentially) trigger `bootstrap_default_tab` on first request rather than at startup (decide based on health-gate semantics — see §3 below)
- `ai-dev/active/F-00086/reports/F-00086_S06_API_report.md`

## Context

You are rewriting `dashboard/routers/chat.py` from a session-scoped surface (`/api/chat/sessions/*`) to a tab-scoped surface (`/api/chat/tabs/*`). The backend layer (S03) already exposes `tab_service` for CRUD, allowlist enforcement, soft-cap, and soft-delete. Your job is the HTTP adapter: request parsing, response shaping, SSE streaming, header emission, and error mapping.

**Old endpoints are removed in the same release** — do NOT keep a compat layer. The frontend (S07) and tests (S08) migrate in lockstep.

## Requirements

### 1. Endpoint surface (exact paths and shapes)

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/chat/tabs` | `{project_id, runtime?, model?, title?, agent?, opencode_session_id?}` | 201 `{tab}` + optional `X-Tab-Soft-Cap-Exceeded: true` |
| GET | `/api/chat/tabs?project_id=X&include_closed=false` | — | 200 `{tabs: [...]}` ordered by `last_active_at DESC` |
| GET | `/api/chat/tabs/{tab_id}` | — | 200 `{tab, session, messages}` |
| PATCH | `/api/chat/tabs/{tab_id}` | `{title?, model?}` | 200 `{tab}` |
| DELETE | `/api/chat/tabs/{tab_id}` | — | 204 |
| POST | `/api/chat/tabs/{tab_id}/reopen` | — | 200 `{tab}` |
| GET | `/api/chat/tabs/{tab_id}/stream` | — | SSE stream (per-tab) |
| POST | `/api/chat/tabs/{tab_id}/prompt` | `{text, model?, context?}` | 204 |
| POST | `/api/chat/tabs/{tab_id}/abort` | — | 204 |
| POST | `/api/chat/tabs/{tab_id}/permissions/{rid}` | `{response, remember?}` | 204 |
| GET | `/api/chat/tabs/recent-closed?project_id=X&limit=10` | — | 200 `{tabs: [...]}` ordered by `closed_at DESC` |

Retained from existing router (no path change):
- `GET /api/chat/config?project_id=X&runtime=opencode` — same response shape (`models`, `default_model`, `default_agent`, `project_directory`); add `runtime` query param defaulting to `"opencode"`
- `GET /api/chat/skills` — unchanged

Removed (do NOT keep):
- `POST /api/chat/sessions`, `GET /api/chat/sessions`, `GET /api/chat/sessions/{sid}`, `GET /api/chat/sessions/{sid}/stream`, `POST /api/chat/sessions/{sid}/prompt`, `POST /api/chat/sessions/{sid}/abort`, `POST /api/chat/sessions/{sid}/permissions/{rid}`

### 2. Request/response Pydantic schemas

Mirror the design's body shapes. Use `BaseModel` with explicit `Field(...)` and minimum-length validation where the design specifies (e.g., `text: str = Field(..., min_length=1)`).

For `PATCH /api/chat/tabs/{tab_id}` — every field optional. Empty body returns the tab unchanged (invariant #8). The PATCH handler calls `tab_service.update_tab(...)` which already implements the "no-op when both args None" semantics — do NOT bump `updated_at` from the router.

### 3. Soft-cap header

`POST /api/chat/tabs` receives `(tab, soft_cap_exceeded)` from `tab_service.create_tab`. When `soft_cap_exceeded` is True, set response header `X-Tab-Soft-Cap-Exceeded: true`. Use FastAPI's `Response` object or return a `JSONResponse(..., headers=...)`. Match the existing router's `Response(status_code=204)` pattern.

### 4. Default-tab bootstrap on first list-tabs

`GET /api/chat/tabs?project_id=X` MUST call `bootstrap_default_tab(db, project_id=X, runtime=runtime, project_repo_root=...)` BEFORE returning the list. The helper itself is the gate — it returns `None` immediately when ANY `chat_tabs` row already exists for the project (active OR closed). Do NOT pre-filter the call on "is the list empty" or `include_closed`: that check would re-fire bootstrap after a user has intentionally closed every tab, resurrecting an arbitrary prior OpenCode session. Pass the call unconditionally on every `GET /api/chat/tabs?project_id=X`; let `bootstrap_default_tab` decide.

This is the seam from AC5 — bootstrap fires lazily on first read, not at app startup, and only when the project has no `chat_tabs` history of any kind.

Resolve `project_repo_root` from the `Project` ORM row (the existing `/api/chat/config` handler already does this — reuse the lookup).

### 5. SSE: `/api/chat/tabs/{tab_id}/stream`

Mirror the existing `stream_session` handler exactly:
- `text/event-stream` content type
- `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive` headers
- Honor `Last-Event-ID` request header AND `last_event_id` query param (existing precedent)
- Keep-alive comment every ~30s
- Disconnect detection via `request.is_disconnected()`
- Subscribe via `relay_manager.get_or_create_relay(tab_id).subscribe(last_event_id=...)`

**Every relayed event already has a `tab_id` field** (set by RelayManager in S03). The SSE formatter just serializes the dict to JSON — do not strip or rename the field.

### 6. Error mapping

| Error from tab_service | HTTP response |
|------------------------|---------------|
| `ValueError("runtime '<x>' not in allowlist {...}")` | 400 `{"error":"<message>"}` |
| `ValueError("model '<x>' not available for runtime '<y>'")` | 400 `{"error":"<message>"}` |
| Tab not found (returns None or raises `NoResultFound`) | 404 `{"error":"tab not found"}` |
| Runtime unhealthy | 503 `{"error":"OpenCode runtime unavailable"}` (preserve existing `_503_unavailable()` helper) |

### 7. Model validation in `POST /api/chat/tabs`

Before calling `tab_service.create_tab`, look up the runtime's `/api/chat/config?runtime=...` `models` list and assert the requested model is in it. If not, return 400 with the message in the table above. This matches Boundary Behavior row "POST /api/chat/tabs with unknown model".

Cache the validation result for the request lifetime (don't refetch on every body field).

### 8. Health-gate dependency

Keep the `_check_runtime_healthy` dependency pattern from the existing router. All tab-scoped endpoints that touch the runtime (create, prompt, abort, permissions, stream, get-with-messages) must 503 when the runtime is unavailable. Pure DB-only endpoints (list, get-without-messages, PATCH, DELETE, reopen, recent-closed) can serve from the DB regardless of runtime health.

### 9. dashboard/app.py wiring

Verify the lifespan still constructs `OpencodeRuntime`, `OpencodeClient`, `RelayManager` and stores them on `app.state`. Update import paths to match the new `orch/chat/opencode/` subpackage. Do NOT call `bootstrap_default_tab` at startup (lazy on first request — §4 above).

## Project Conventions

Read `dashboard/CLAUDE.md` — routers are thin, business logic in `orch/`, htmx posts return fragments NOT JSON for action endpoints. The chat router is an **API surface** (JSON-only), so it does NOT return HTML fragments — see existing chat.py for the established pattern.

## TDD Requirement

Capture a RED run for `tests/integration/test_chat_tabs_api.py::test_post_tabs_rejects_unknown_runtime` (or a similar new test in `tests/integration/test_chat_tabs_api.py`) — that test asserts HTTP 400 on `{"runtime":"pi"}` and will fail against pre-S06 code with `assert 404 == 400` because the endpoint does not exist yet. **S08 owns the full integration test file**; S06 may write a single targeted test as RED evidence and pass it as part of the GREEN implementation.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`
4. `uv run pytest tests/dashboard/test_chat_*.py -v` — most will still fail because they assert against old paths; that's expected and S08 fixes them. Capture and report the count so reviewers can verify the failures are path-related, not behavioural.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "api-impl",
  "work_item": "F-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/chat.py",
    "dashboard/app.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "",
  "tdd_red_evidence": "tests/integration/test_chat_tabs_api.py::test_post_tabs_rejects_unknown_runtime — assert 404 == 400 (endpoint did not exist pre-S06)",
  "blockers": [],
  "notes": "Existing tests/dashboard/test_chat_*.py asserts against old paths; S08 migrates them."
}
```
