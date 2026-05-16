# I-00086_S01_API_prompt

**Work Item**: I-00086 -- Runtime override controls give no UI feedback
**Step**: S01
**Agent**: api-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers spun up by pytest fixtures; read-only introspection (`docker ps`, `docker inspect`, `docker logs`); invoking `./ai-core.sh` or `make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch alembic migrations. You MUST NOT run `alembic upgrade`/`downgrade`/`stamp` against the live DB.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00086 --json` over the manifest file.
- `ai-dev/active/I-00086/I-00086_Issue_Design.md` — design document (READ FIRST)
- `dashboard/routers/runtime_overrides.py` — file you will modify
- `dashboard/routers/items.py` — read the existing item-overview render path (around line 1237) to understand how `fragments/item_overview.html` is rendered and what context it needs
- `dashboard/templates/fragments/item_overview.html` — current template; you do NOT modify it in this step (S03 does)
- `dashboard/routers/staleness.py` (around line 132) — precedent for `HX-Trigger.showToast` response header

## Output Files

- `ai-dev/active/I-00086/reports/I-00086_S01_API_report.md` — Step report

## Context

You are fixing the API side of incident **I-00086**: both PATCH endpoints in `dashboard/routers/runtime_overrides.py` currently return `Response(status_code=204)` with no body and no `HX-Trigger` header. The frontend uses `hx-swap="none"` and therefore swaps nothing and shows nothing. Users see no feedback.

This step rewrites the **response shape** of both endpoints. The frontend wiring (changing `hx-target`/`hx-swap`, and extracting a sub-fragment) is S03's job — you do NOT edit the template in this step. Your changes must be valid in isolation: existing tests against these endpoints will need to be updated by S05, but your code must not crash if the template currently has `hx-swap="none"`.

Read the design document `ai-dev/active/I-00086/I-00086_Issue_Design.md` first — specifically the **Root Cause Analysis**, **Acceptance Criteria** (AC1, AC2, AC3), and **TDD Approach** sections.

## Requirements

### 1. Render helper for the steps-table fragment

The new endpoint responses both return the rendered **steps table** as an HTML fragment in the body. To avoid duplicating the fragment-rendering logic (which currently lives inline in `dashboard/routers/items.py` near line 1237), do one of the following — pick whichever is cleaner:

- **Preferred**: extract a small helper, e.g. `_render_steps_table(db, project_id, item_id) -> str`, in a new module or alongside the existing renderer. The helper must:
  1. Load the WorkItem (404 if absent).
  2. Load all WorkflowSteps for that item in the same order the overview page renders them.
  3. Load the enabled `agent_runtime_options` (sort_order, id) — same shape the page uses (`runtime_options_list` in `items.py:1130`/`:1220`).
  4. Render `fragments/item_steps_table.html` (new template that S03 will create) with the same `item`, `steps`, `runtime_options`, and any other context variables the existing overview render passes (e.g. `run_count` for the lazy run-list container).
  5. Return the rendered HTML string.
- **Acceptable fallback** if extracting the helper is impractical for this step: in this step S01, render `fragments/item_overview.html` via the existing item-overview path and return that as the body. S03 will then extract `fragments/item_steps_table.html` and the API will start returning that instead. **If you take this fallback, document it clearly in your report so S03 picks it up.**

The template name `fragments/item_steps_table.html` does NOT exist yet — S03 will create it. Your render call may therefore fail at import-time if you guard it incorrectly. Two options:

- Render the full overview fragment in this step (the fallback above), and let S03 swap the template name to `fragments/item_steps_table.html` when it creates it; OR
- Add a one-line stub `dashboard/templates/fragments/item_steps_table.html` that contains a comment plus `{% include "fragments/item_overview.html" %}` to keep imports green. **If you create the stub, mark it clearly so S03 replaces it with the real extraction.**

Either approach is fine. Document which one you picked in the report.

### 2. Update `patch_step_runtime_override` (single-step PATCH)

Current: returns `Response(status_code=204)`.

New behavior:

1. After the existing validation and DB-mutation logic completes successfully (and the existing `emit_runtime_override_changed` call still fires), construct the response as:
   - HTTP status: **200**
   - `Content-Type: text/html; charset=utf-8`
   - Body: the rendered steps-table fragment from the helper in (1)
   - `HX-Trigger` header: JSON-encoded `{"showToast": {"message": "Model updated", "type": "success"}}`
2. The 404 / validation paths (item not found, option_id not found in enabled runtime_options) must continue to raise `HTTPException(404, ...)` with no `HX-Trigger` and no body change.
3. Preserve the existing `_get_item_or_404`, `_validate_option_id`, and `emit_runtime_override_changed` call sites — only the response-construction lines change.

Use `json.dumps({"showToast": {...}})` for the `HX-Trigger` header value — matching the precedent in `dashboard/routers/staleness.py:132`.

Use FastAPI's `HTMLResponse` (or `Response` with explicit media type) — do not import a new framework.

### 3. Update `patch_bulk_runtime_override` (bulk PATCH)

Current: returns `Response(status_code=204)`.

New behavior:

1. After the existing query collects `editable_steps`, compute `updated_count = len(editable_steps)`.
2. **Success branch** (`updated_count >= 1`):
   - Apply the override as today, emit the existing `runtime_override_changed` DaemonEvent.
   - Build the response:
     - HTTP status: **200**
     - Body: rendered steps-table fragment.
     - `HX-Trigger` header: `{"showToast": {"message": f"Model updated for {updated_count} step(s)", "type": "success"}}`.
3. **Zero-eligible-steps branch** (`updated_count == 0`):
   - Do NOT emit a DaemonEvent (preserve existing behavior — no event, no DB write).
   - Build the response:
     - HTTP status: **200**
     - Body: rendered steps-table fragment (the table is unchanged — re-rendering is still safe and idempotent and keeps client + server in sync).
     - `HX-Trigger` header: `{"showToast": {"message": "No editable steps to update", "type": "info"}}`.
4. Validation paths (item not found, option_id not found) continue to raise 404.

Note: the `updated_count` is the number of editable steps the endpoint **actually changed**, NOT the total step count of the item. Do not include synthetic steps (`MERGE`, `S00`) or any step whose status is outside `_EDITABLE_STEP_STATUSES`.

### 4. Do NOT modify

- `dashboard/templates/fragments/item_overview.html` — S03 owns template changes.
- `dashboard/templates/pages/project/item_detail.html` — the toast hook already exists at line 158-167; do not duplicate it.
- The CSS file (`dashboard/static/styles.css`) — no new classes are required.
- The route paths / URL shapes — only response shape changes.
- The body of `emit_runtime_override_changed` — call sites unchanged.

### 5. Mandatory inline note

Add a short comment near the new response construction in each endpoint (1-2 lines) explaining the contract: response is the steps-table fragment, `HX-Trigger.showToast` drives the user-visible feedback. Do NOT write a paragraph — one line, factual.

## Project Conventions

Read `dashboard/CLAUDE.md` for:

- Fragment-template rule: fragments under `templates/fragments/` MUST NOT extend `base.html`.
- "Routers are thin" — keep the render helper close to other render code rather than putting business logic in the router.
- `dependencies.py:get_db()` pattern for the DB session.

Follow `CLAUDE.md` rules exactly. When in doubt, match `dashboard/routers/staleness.py:132` and surrounding lines.

## TDD Requirement

This step modifies an API contract. The Tests step (S05) writes the full reproduction + regression suite, but you must still verify your own work with at least one targeted test you write in S01 OR with a manual `curl`/pytest invocation that proves:

1. **RED**: Before your change, a quick `pytest tests/dashboard/test_runtime_overrides.py -v` (or `curl -i -X PATCH ...`) shows the current 204. Record the failure mode in `tdd_red_evidence`.
2. **GREEN**: After your change, the same invocation shows 200 + `HX-Trigger` header + non-empty body.

Do NOT run the full test suite — the QV gates at S12 (`unit-tests`) and S13 (`integration-tests`) own that.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run:

1. `make format` — fix any drift in the files you touched.
2. `make typecheck` — zero new errors in `dashboard/routers/runtime_overrides.py` (and any helper you added).
3. `make lint` — zero errors in the same files.

Populate `preflight` in your result contract.

## Test Verification (NON-NEGOTIABLE)

After implementation, run only the tests that exercise your code:

```bash
uv run pytest tests/dashboard/test_runtime_overrides.py -v
```

If that file doesn't exist yet (S05 will create the full set), run the existing tests for these endpoints:

```bash
uv run pytest tests/ -k runtime_override -v
```

Do NOT run `make test-unit` or `make test-integration` — those are S12/S13.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "api-impl",
  "work_item": "I-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/runtime_overrides.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_runtime_overrides.py::test_bulk_returns_fragment — AssertionError: assert 204 == 200  // captured RED run before change",
  "blockers": [],
  "notes": "Document here: (a) which render approach you took for requirement (1) — helper extraction vs. fallback; (b) whether you created a stub fragments/item_steps_table.html for S03 to replace."
}
```
