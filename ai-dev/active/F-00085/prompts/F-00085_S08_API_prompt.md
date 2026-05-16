# F-00085_S08_API_prompt

**Work Item**: F-00085
**Step**: S08
**Agent**: api-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations in this step.

## Input Files

- `ai-dev/active/F-00085/F-00085_Feature_Design.md` — endpoint list, ACs, validation rules
- S01 deliverables (already merged): `merge_auto_verdicts` + `auto_merge_project_config` ORM models
- S04 / S06 deliverables (already merged): event-type constants, aggregator queries, `resolve_project_config`
- Existing patterns:
  - `dashboard/routers/jobs_ui.py` — best precedent (page route + multiple htmx fragment routes + JSON endpoint + per-item detail)
  - `dashboard/routers/items.py` — POST endpoint pattern, request body validation
  - `dashboard/app.py` — router registration

## Output Files

- `ai-dev/active/F-00085/reports/F-00085_S08_API_report.md`

## Context

Implement the 7 dashboard endpoints under `/<project>/auto-merge`. They expose the aggregator queries (S06) as htmx fragments + JSON; they validate write requests and emit audit events.

No template files here (those are S10). API responses are either `HTMLResponse` (rendering a fragment that S10 will create) or `JSONResponse`. To avoid blocking S10, the router can render placeholder strings for any template that S10 hasn't created yet — but each fragment template path MUST be referenced by name (S10 will create the matching files).

## Requirements

### 1. New router file `dashboard/routers/auto_merge_ui.py`

Mirror `dashboard/routers/jobs_ui.py` for the page + fragment pattern. Use:

```python
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from dashboard.dependencies import get_db, get_templates, current_project
from orch import auto_merge_aggregator as agg
from orch.daemon.auto_merge import (
    AutoMergeConfig,
    EVENT_AUTO_MERGE_CONFIG_UPDATED,
)
from orch.db.models import (
    AgentRuntimeOption,
    AutoMergeProjectConfig,
    DaemonEvent,
    MergeAutoVerdict,
)
from pathlib import Path as FsPath
from sqlalchemy import select
import subprocess
import difflib

router = APIRouter()

EXECUTOR_TOML = FsPath(__file__).resolve().parents[2] / "executor" / "auto_merge.toml"
MAX_VERDICT_NOTES_BYTES = 8192
```

### 2. Seven endpoints

#### GET `/<project_id>/auto-merge` → page render

- Path: `/{project_id}/auto-merge`, `response_class=HTMLResponse`.
- Loads `toml_config = AutoMergeConfig.load(EXECUTOR_TOML)[0]`.
- Calls `agg.get_status_snapshot(db, project_id, toml_config)`.
- Renders `pages/project/auto_merge.html` with context: `status`, `project`, `runtime_options` (enabled rows from `agent_runtime_options`, grouped by `cli_tool`).
- If `status.config.phase == 0`: still render the page, but the template branches to the "plumbing-only" empty state (AC6).

#### GET `/<project_id>/auto-merge/status` → status chip fragment

- Returns `fragments/auto_merge_status_chip.html` rendered with the same `status` from `get_status_snapshot`.
- This endpoint is what `base.html` includes via htmx; it must be cheap (single status snapshot query).
- Cache hint: htmx `hx-trigger` set in the template to refresh on a 30s interval; this endpoint must remain idempotent and side-effect-free.

#### GET `/<project_id>/auto-merge/events` → events table fragment

- Query params: `page` (int, default 0, min 0), `type` (optional string filter on event_type), `page_size` (int, default 50, max 200).
- Calls `agg.list_recent_events(db, project_id, page=page, page_size=page_size, event_type_filter=type)`.
- Returns `fragments/auto_merge_events_table.html` rendered with `rows`, `total`, `page`, `page_size`, `has_more`.

#### GET `/<project_id>/auto-merge/events/{event_id}` → event detail modal

- Calls `agg.get_event_detail(db, project_id, event_id)` → returns `EventRow | None`.
- 404 if None.
- For `merge_auto_resolved` events: build diff data for each file in `llm_calls`:
  ```python
  for call in event.metadata.get("llm_calls", []):
      file_path = call.get("file_path")
      proposed = call.get("proposed_content", "")
      try:
          current = subprocess.run(
              ["git", "show", f"main:{file_path}"],
              capture_output=True, text=True, timeout=10, check=False,
              cwd=<repo root>,
          )
          if current.returncode == 0:
              current_text = current.stdout
          else:
              current_text = None  # file no longer on main
      except subprocess.TimeoutExpired:
          current_text = None
          fetch_error = "timeout"
      diff_html = difflib.HtmlDiff(wrapcolumn=80).make_table(
          proposed.splitlines(),
          (current_text or "").splitlines(),
          fromdesc="Proposed by LLM",
          todesc="Currently on main" if current_text else "(file no longer exists on main)",
      ) if proposed else None
  ```
- Returns `fragments/auto_merge_event_detail.html` rendered with `event`, `diffs` (list of `{file_path, diff_html, current_available}`), `verdict` (from row).

#### POST `/<project_id>/auto-merge/events/{event_id}/verdict` → set verdict

- Request body: `{"verdict": "pending|correct|wrong|partial", "notes": "<string, max 8KB>"}`.
- Validation:
  - Verdict must be one of the four allowed values (HTTP 400 with explanation otherwise).
  - Notes ≤ `MAX_VERDICT_NOTES_BYTES` bytes (HTTP 413 otherwise).
  - The referenced event MUST exist and MUST be of type `merge_auto_resolved` (HTTP 400 "verdicts only apply to merge_auto_resolved events" otherwise — Boundary table).
- Upserts `merge_auto_verdicts` with `ON CONFLICT (project_id, daemon_event_id) DO UPDATE`.
- Returns the re-rendered row fragment (htmx-friendly) OR JSON `{ok: true, verdict: "..."}` when the request `Accept` header is JSON.

#### POST `/<project_id>/auto-merge/config` → upsert per-project config

- Request body: `{"phase": 0|1|null, "runtime_option_id": <int>|null}`.
- Validation:
  - `phase` must be 0, 1, or null (HTTP 400 "phases 2 and 3 are reserved for future CRs" otherwise — Inv 5).
  - `runtime_option_id` must reference an `agent_runtime_options.id` where `enabled=True` (HTTP 400 with `{"error": "runtime_option <id> is disabled — pick an enabled row"}` otherwise — AC14).
  - `runtime_option_id` may be null (clear runtime override).
- Loads existing row (if any) for the before/after audit.
- Upserts `auto_merge_project_config` with `ON CONFLICT (project_id) DO UPDATE SET phase=…, runtime_option_id=…, updated_at=now(), updated_by=<sentinel>`.
- If BOTH `phase` and `runtime_option_id` are null in the request, you MAY delete the row instead of writing nulls — both behaviours satisfy AC13 (clear override).
- Emits an `auto_merge_config_updated` DaemonEvent with metadata:
  ```json
  {
    "old": {"phase": <prev or null>, "runtime_option_id": <prev or null>},
    "new": {"phase": <new>, "runtime_option_id": <new>},
    "updated_by": "dashboard",
    "source": "dashboard"
  }
  ```
- Returns the re-rendered status chip fragment (htmx swap) OR JSON when JSON-accept.

#### GET `/<project_id>/auto-merge/rollup` → verdict + cost rollup

- Query param: `window` (`7d` or `30d`, default `7d`).
- Calls `agg.get_verdict_rollup(...)` AND `agg.get_token_cost_rollup(...)` AND `agg.get_refuse_list_breakdown(...)`.
- Returns `fragments/auto_merge_rollup.html` rendered with the three result objects.

### 3. Register router in `dashboard/app.py`

Add one import + one `app.include_router(auto_merge_ui.router, prefix="", tags=["auto-merge"])` (or whatever prefix matches the project-id-in-path pattern of `jobs_ui.py`).

### 4. Operator identity for `updated_by` / `verdicted_by`

The dashboard does not have auth today. Use the sentinel `"dashboard"` for `updated_by` / `verdicted_by`. If `request.headers.get("X-Operator")` is set (future hook), prefer that. Do NOT log IP addresses.

### 5. Disabled-runtime defence in depth (AC14)

Two layers:
- The Settings template (S10) builds its `<option>` list from `enabled=True` rows only.
- This API endpoint independently re-validates that the chosen id is currently `enabled=True`. If a row gets disabled between page render and POST, the API rejects with 400 — UI cannot bypass this.

### 6. Subprocess `git show main:<file>` safety

- Always run with `cwd=<repo root>` (find via `Path(__file__).resolve().parents[2]` or similar — match existing router conventions).
- `timeout=10` seconds. On timeout → `current_available=False` + placeholder in template.
- `check=False` — handle non-zero returncode gracefully (file not on main → `current_text=None`).
- Never raise unhandled exceptions to FastAPI — wrap the whole diff section in try/except → fall back to placeholder.

## Project Conventions

- Read `dashboard/CLAUDE.md` for router conventions.
- Use existing template DI via `get_templates()`.
- Use existing DB session DI via `get_db()`.
- Match the path/prefix pattern of `dashboard/routers/jobs_ui.py` (project_id in path).
- Pydantic request bodies are OK; explicit type hints required.

## TDD Requirement

- **RED**: write a failing test in `tests/dashboard/test_auto_merge_routes.py` per endpoint: starts as a 404/501 because the router isn't wired yet, OR 422 because pydantic body doesn't exist. Capture the first failure.
- **GREEN**: implement endpoints until all targeted tests pass.

The full AC coverage matrix lives in S13; your responsibility is enough RED→GREEN to validate each endpoint's contract.

Capture RED failure line in your report.

## Pre-flight Quality Gates

1. `make format`.
2. `make typecheck`.
3. `make lint`.
4. Targeted: `uv run pytest tests/dashboard/test_auto_merge_routes.py -v`.

## Test Verification

- Run only the dashboard route tests you wrote.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "api-impl",
  "work_item": "F-00085",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/routers/auto_merge_ui.py",
    "dashboard/app.py",
    "tests/dashboard/test_auto_merge_routes.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed (targeted dashboard route tests for 7 endpoints)",
  "tdd_red_evidence": "tests/dashboard/test_auto_merge_routes.py::test_get_status_returns_404_before_wiring — assert 404 == 200",
  "blockers": [],
  "notes": "All 7 endpoints wired; defence-in-depth on disabled runtime (template build + API re-validation); subprocess git show wrapped in try/except + timeout; updated_by sentinel = 'dashboard' until auth lands."
}
```
