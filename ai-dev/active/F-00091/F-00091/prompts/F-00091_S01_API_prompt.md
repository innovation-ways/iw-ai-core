# F-00091_S01_API_prompt

**Work Item**: F-00091 -- AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar
**Step**: S01
**Agent**: api-impl

---

## ⛔ Docker is off-limits

Standard policy. This step touches no Docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step adds no migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00091 --json`
- `ai-dev/active/F-00091/F-00091_Feature_Design.md` — Design document (read the Scope, AC1, and Invariant 4 carefully)
- `dashboard/routers/chat.py` — Where the new endpoint must live
- `dashboard/routers/projects.py:144` — Reference for `nav_projects` shape (returns HTML; this new endpoint returns JSON)
- `orch/db/models.py` — `Project` model (search for `class Project`)

## Output Files

- `ai-dev/work/F-00091/reports/F-00091_S01_API_report.md` — Step report (per the Subagent Result Contract below)

## Context

You are adding a small JSON endpoint that the Assistant's new project dropdown will consume. The endpoint lives in the same router module as the rest of the chat API so it sits alongside `/api/chat/tabs`, `/api/chat/config`, etc.

Read the design doc first, especially:

- **Scope → S01** for the contract
- **AC1** for how the dropdown consumes the response
- **Invariant 4** — only `enabled = true` projects must appear
- **Boundary Behavior** rows for empty list and stale selected project

Read `CLAUDE.md` for project-specific patterns and conventions.

## Requirements

### 1. New endpoint: `GET /api/chat/projects`

Add to `dashboard/routers/chat.py`. The endpoint MUST:

- Be registered on the same `router` instance the rest of the file uses (the router has `prefix=""` or `prefix="/api/chat"` — match what is already there; do NOT introduce a new prefix).
- Accept no query parameters in v1.
- Return JSON with the exact shape:
  ```json
  {
    "projects": [
      {"id": "iw-ai-core", "display_name": "IW AI Core Platform"},
      {"id": "innoforge",  "display_name": "InnoForge Document Platform"}
    ]
  }
  ```
- Query the `Project` table via the `db: Session = Depends(get_db)` pattern already used elsewhere in this file.
- Filter `WHERE enabled = true` (per Invariant 4).
- Sort alphabetically by `display_name` (case-insensitive, ascending) — this is the order the dropdown will render.
- Return HTTP 200 with an empty list when no enabled projects exist (do NOT 404).
- Be importable and registered automatically because the router is already mounted in `dashboard/app.py`. Confirm this by reading the existing endpoint registrations in the file.

### 2. Match the surrounding style

- Use the same `async def` + `Depends(get_db)` pattern as `list_tabs` and `get_tab` in the same file.
- Do NOT add a Pydantic model for the response; the surrounding endpoints return raw dicts.
- Do NOT add auth — the rest of `dashboard/routers/chat.py` has none.
- Type-annotate the return as `dict[str, Any]` (consistent with the file's existing endpoint signatures).
- Add a one-paragraph docstring explaining the endpoint's purpose, citing F-00091.

### 3. TDD — write the test first

Create `tests/dashboard/test_api_chat_projects.py` (or extend the existing nearest dashboard test module for chat — confirm location during impl). The test MUST:

- Insert three `Project` rows: two with `enabled=true` and different display_names, one with `enabled=false`.
- Hit `GET /api/chat/projects` via `TestClient`.
- Assert HTTP 200.
- Assert the response shape exactly matches the contract above.
- Assert ONLY the two enabled rows appear, in alphabetical order by `display_name`.
- Assert the disabled row is NOT in the response.

Add a SECOND test for the empty-list case (no projects in the DB → empty array).

Run the test, **capture the RED failure**, then implement the endpoint, then re-run for GREEN. Record both in `tdd_red_evidence`.

### 4. Do NOT touch anything else

This step has a single concern. Do NOT modify `chat.js`, `panel.html`, the chat-tab service, or the Project model. The next steps consume your endpoint; they own the rest.

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries (`dashboard/routers/` are thin; business logic stays in `orch/`)
- Coding conventions and naming rules
- ORM style (SQLAlchemy 2.0 sync, `Mapped[]` declarative)
- Test organization (dashboard tests use `TestClient`; never connect to live DB on 5433 — testcontainers only)
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write the failing tests first. Run only the new test file (`uv run pytest tests/dashboard/test_api_chat_projects.py -v`). Confirm the failure is the expected one (most likely `404` or `AttributeError` because the endpoint doesn't exist yet). Capture the failing assertion line.
2. **GREEN**: Add the endpoint to `dashboard/routers/chat.py`. Re-run the test.
3. **REFACTOR**: Tidy without changing behaviour.

Do not skip the RED phase.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run:

1. `make format` — auto-fixes formatting drift; inspect the diff and re-stage if anything changed.
2. `make typecheck` — must report zero new errors involving the files you touched.
3. `make lint` — must report zero errors involving the files you touched.

Record each in the `preflight` object: `"ok"` | `"fixed"` | `"skipped:<reason>"`.

## Test Verification (NON-NEGOTIABLE)

Run only the test file(s) you wrote:

```bash
uv run pytest tests/dashboard/test_api_chat_projects.py -v
```

Do **NOT** run `make test-integration` or `make test-unit` here — those are S16/S18 QV gates.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "api-impl",
  "work_item": "F-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/chat.py",
    "tests/dashboard/test_api_chat_projects.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_api_chat_projects.py::test_lists_enabled_projects_alpha — assert response.status_code == 200, got 404",
  "blockers": [],
  "notes": ""
}
```
