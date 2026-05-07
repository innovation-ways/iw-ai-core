# F-00080_S01_api-impl_prompt

**Work Item**: F-00080 — First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)
**Step**: S01
**Agent**: api-impl

---

## ⛔ Docker is off-limits

Standard policy. Read the boilerplate in `ai-dev/templates/Implementation_Prompt_Template.md` if you need the full list. Allowed exceptions: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh` / `make` targets.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This step does NOT touch migrations** — there is no DB change.

## Input Files

- Runtime step state: prefer `uv run iw item-status F-00080 --json`.
- `ai-dev/active/F-00080/F-00080_Feature_Design.md` — full design doc
- `dashboard/CLAUDE.md` — dashboard layer rules
- Existing routers for pattern reference: `dashboard/routers/research.py`, `dashboard/routers/docs.py`

## Output Files

- `dashboard/routers/help.py` — new router
- `dashboard/app.py` — register the router
- `ai-dev/work/F-00080/reports/F-00080_S01_api_report.md` — step report

## Context

You are creating the help fragment delivery endpoint. The dashboard pages will declare a help slug; the frontend will htmx-GET `/_help/<slug>` and inject the rendered fragment as a popover. The endpoint is read-only, has no DB calls, has no query params other than the slug path parameter, and renders one Jinja partial under `dashboard/templates/_partials/help/<slug>.html`.

The fragment files themselves are created by S03 (frontend-impl). You only need to create the router and write tests for it. **Do not create the fragment files yourself — but do verify that the slug allow-list mechanism handles the case where 0 fragments exist on disk yet (your tests must run before S03 runs).**

## Requirements

### 1. Create `dashboard/routers/help.py`

- Use `APIRouter()` with no prefix (the path is exactly `/_help/{slug}`).
- Compute the allow-list of valid slugs **at startup** by listing `dashboard/templates/_partials/help/*.html` and stripping the `.html` suffix. Cache it in a module-level set for O(1) lookup. Re-reading the directory on every request is fine in dev but not necessary; use one read at import time.
- The slug **must** match the regex `^[a-z][a-z0-9_-]{0,31}$`. Reject anything else with HTTP 404 (do not 400 — we want path traversal attempts to look like ordinary "not found" to a probe).
- If the slug is in the allow-list, render `_partials/help/<slug>.html` via the existing Jinja2 templates instance and return `HTMLResponse`.
- If the slug is not in the allow-list, return `HTTPException(status_code=404, detail="No help available for this page")`.
- Do **not** call `os.path` joins on user input — use the validated slug to build the template name directly: `f"_partials/help/{slug}.html"`. Templates are looked up by Jinja, not by raw filesystem; path traversal through Jinja's loader requires `..` in the slug, which the regex blocks.
- The endpoint takes no query parameters and no request body.
- Add a docstring on the route function noting: "Read-only. Returns a Jinja help fragment by slug. See F-00080."

### 2. Register the router in `dashboard/app.py`

- Match the existing pattern used for other routers (e.g. `from dashboard.routers import help as help_router; app.include_router(help_router.router)`).
- Place the include alongside the other dashboard router includes — preserve alphabetical or grouped order if one exists.
- The module name `help` shadows a Python builtin only via `import` aliasing — use `help as help_router` to avoid the shadow.

### 3. Behaviour for the empty-allow-list edge case

Until S03 lands, the directory `dashboard/templates/_partials/help/` may not exist. Your code must:

- If the directory is missing or empty, log a one-time `WARNING` at startup ("Help fragments directory not found; /_help endpoint will return 404 for all slugs.") and proceed with an empty allow-list.
- The endpoint must remain registered and return 404 for every slug in this case.
- Do **not** raise at import time — that would crash the dashboard.

### 4. Do NOT create fragment files in this step

S03 is responsible for the 22 fragments. Your unit tests in this step should mock the allow-list (monkeypatch the module-level set) rather than relying on real fragments existing.

### 5. Write minimal unit tests for the router behaviour (RED phase)

Add to `tests/dashboard/test_help_router.py` (it does not yet exist):

- Test 1: Patch the allow-list to include `["queue"]`, GET `/_help/queue` → 200, content-type `text/html`, body contains the literal slug name (you can verify by also patching the Jinja loader or by writing a temporary fragment in `tmp_path`).
- Test 2: Patch the allow-list to `["queue"]`, GET `/_help/unknown` → 404.
- Test 3: GET `/_help/../etc/passwd` → 404 (the regex rejects). Body must NOT contain `/etc/passwd` content.
- Test 4: GET `/_help/UPPERCASE` → 404 (regex rejects uppercase).
- Test 5: GET `/_help/queue?foo=bar` → still 200; query string is ignored.

These tests will go GREEN once your implementation is in place. The full set of slug-by-slug tests (one per real fragment) is owned by S07 (tests-impl).

## Project Conventions

Read root `CLAUDE.md` and `dashboard/CLAUDE.md`.

- Routers are thin — no business logic, no DB calls.
- Use `HTMLResponse` for HTML returns.
- Jinja2 templates instance: get it from the existing pattern in other routers (`from dashboard.dependencies import templates` or however it is imported in your codebase — verify by reading e.g. `dashboard/routers/docs.py`).
- Type hints on all public functions.
- No emojis in code or comments.

## TDD Requirement

Follow Red-Green-Refactor. Write the 5 tests above first; they should FAIL (router doesn't exist yet). Then implement the router. Then re-run; they should pass.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run:

1. `make format` — auto-fixes formatting drift.
2. `make typecheck` — must report zero errors involving the files you touched.
3. `make lint` — must report zero errors.

Populate `preflight` in the result contract (`ok` / `fixed` / `skipped:<reason>`).

## Test Verification

Run `make test-unit` (or `pytest tests/dashboard/test_help_router.py -q` for a fast loop). All 5 tests must pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "api-impl",
  "work_item": "F-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/help.py",
    "dashboard/app.py",
    "tests/dashboard/test_help_router.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
