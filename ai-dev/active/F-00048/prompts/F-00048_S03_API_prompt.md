# F-00048_S03_API_prompt

**Work Item**: F-00048 -- Code Understanding: Module + Symbol Views
**Step**: S03
**Agent**: api-impl

---

## Input Files

- `ai-dev/active/F-00048/F-00048_Feature_Design.md` -- Design document
- `ai-dev/work/F-00048/reports/F-00048_S01_Backend_report.md` -- S01 report (backend implemented)
- `ai-dev/work/F-00048/reports/F-00048_S02_CodeReview_report.md` -- S02 review (backend approved)
- `orch/rag/parser.py` -- parse_modules_from_level1() (from S01)
- `orch/rag/module_gen.py` -- ModuleGenerator (from S01)
- `orch/rag/symbol_gen.py` -- SymbolGenerator (from S01)
- `orch/doc_service.py` -- DocService for ProjectDoc lookup
- `dashboard/routers/` -- existing router files for pattern reference
- `dashboard/dependencies.py` -- get_db() dependency

## Output Files

- `dashboard/routers/code.py` -- **EXTEND** the existing router created by F-00046. Add 4 new endpoints to the existing `APIRouter` instance. Do NOT create a new file, do NOT create a second router object, do NOT touch `dashboard/app.py`.
- `tests/integration/test_code_module_routes.py` -- integration tests for the 4 new endpoints (separate file from F-00046's `test_code_index_pipeline.py`)
- `ai-dev/work/F-00048/reports/F-00048_S03_API_report.md` -- Step report

## Context

You are implementing the API layer for **F-00048: Code Understanding: Module + Symbol Views**.

S01 (backend-impl) has already implemented `ModuleGenerator`, `SymbolGenerator`, and `parse_modules_from_level1()`. Your job is to add 4 FastAPI endpoints to the **existing** `dashboard/routers/code.py` (created by F-00046) and write integration tests for each new endpoint.

**CRITICAL — DO NOT**:
- Do NOT create `dashboard/routers/code.py` — it already exists with 5 indexing/status endpoints.
- Do NOT create a new `APIRouter` instance — reuse the existing `router` object in that file.
- Do NOT modify `dashboard/app.py` — the router is already registered there by F-00046.
- Do NOT rename, move, or alter the existing 5 endpoints in the file.

Read the design document, `dashboard/routers/code.py` (as it exists after F-00046 merge), all S01/S02 output files, and `CLAUDE.md` before writing any code. Study `dashboard/routers/items.py` and `dashboard/routers/actions.py` for the project's router pattern.

## Requirements

### 1. dashboard/routers/code.py — Add 4 endpoints to existing router

The `APIRouter` is already defined with prefix `/api/projects/{project_id}/code` and tag `code` (created by F-00046). **Reuse** that `router` object — do not instantiate a new one. Add the 4 new endpoint handlers and any new imports at the top of the file, alongside the existing 5 endpoints.

Follow the project convention: routes are thin. All business logic stays in `orch/` — routers only validate inputs, call the appropriate `orch/` function, and return responses.

All four endpoints return **HTML fragments** via `templates.TemplateResponse(...)` — NOT JSON. These endpoints are htmx-driven and the response is inserted directly into the DOM. See the F-00047 router pattern for `code_architecture_view.html` and match it exactly.

Markdown-to-HTML conversion must happen server-side. Use the existing `markdown` Python package (already in project deps, used by other doc fragments — grep for `markdown.markdown(` to find the pattern). If no existing helper exists, add a small `_render_markdown(text: str) -> str` function at the top of `dashboard/routers/code.py` or in `orch/doc_service.py` and reuse it.

#### GET /api/projects/{project_id}/code/modules

```python
@router.get("/modules")
async def list_modules(
    project_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """
    1. Look up Level 1 ProjectDoc for the project via DocService.
       Verify the actual slug pattern used by F-00046's MapGenerator — do NOT guess.
       Grep `orch/rag/mapgen.py` for `slug=` to find the exact pattern.
    2. If not found: return a 404 HTML fragment (reuse the existing empty-state fragment
       from F-00047 if present, otherwise a minimal inline error).
    3. Call parse_modules_from_level1(doc.content)
    4. Render fragments/code_module_cards.html with {modules, project_id, source_doc_slug}
    """
```

Note: the `APIRouter` already has prefix `/api/projects/{project_id}/code`, so this decorator is `@router.get("/modules")`, NOT `@router.get("/{project_id}/code/modules")`. The prefix is added automatically. Match the decorator pattern of the existing 5 endpoints in the file.

#### GET /api/projects/{project_id}/code/modules/{module_slug}

```python
@router.get("/modules/{module_slug}")
async def get_module(
    project_id: str,
    module_slug: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """
    1. Look up Level 1 doc, parse modules, find entry matching module_slug.
    2. If not found: return 404 HTML fragment.
    3. Build CodeUnderstandingConfig from project.config.
    4. Launch generation and wait up to 500ms (see timeout pattern below).
    5. Render fragments/code_module_detail.html with:
       {project_id, module, doc_html, was_cached, generating}
       where doc_html is the server-rendered HTML of doc.content (markdown), or None if generating.
    """
```

For the 500ms timeout check, use `asyncio.shield` so the underlying task is NOT cancelled when the wait times out — otherwise the generation work is thrown away and the client polls forever:

```python
task = asyncio.create_task(gen.get_or_generate(project_id, module_path, module_name, config, session))
try:
    doc, was_cached = await asyncio.wait_for(asyncio.shield(task), timeout=0.5)
    return {"doc": {...}, "was_cached": was_cached, "generating": False}
except asyncio.TimeoutError:
    # Task is still running in the background. The next poll will check the cache
    # via get_or_generate and return the doc once the task has written it.
    return {"doc": None, "was_cached": False, "generating": True}
```

The background task will complete on its own; subsequent GET polls re-enter `get_or_generate()`, which returns the freshly-written `ProjectDoc` from cache on the next call. Note: there is no unique constraint on `project_docs.slug`, so concurrent duplicate work is possible — see the "Concurrency Note" in the design's Invariants section.

Note: The project config's `code_understanding` key is a dict parsed via `CodeUnderstandingConfig(**project.config.get("code_understanding", {}))`.

#### POST /api/projects/{project_id}/code/modules/{module_slug}/generate

```python
@router.post("/modules/{module_slug}/generate")
async def regenerate_module(
    project_id: str,
    module_slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """
    1. Look up Level 1 doc, parse modules, find entry matching module_slug.
    2. If not found: return 404 HTML fragment.
    3. Delete existing ProjectDoc for the computed slug (via DocService) if present.
    4. Call ModuleGenerator().generate_level2(...) directly — do NOT call get_or_generate.
    5. Render fragments/code_module_detail.html with was_cached=False and
       doc_html=markdown_to_html(doc.content).
    """
```

#### GET /api/projects/{project_id}/code/symbol

```python
@router.get("/symbol")
async def explain_symbol(
    project_id: str,
    file_path: Annotated[str, Query(..., description="Relative file path within the repo")],
    db: Annotated[AsyncSession, Depends(get_db)],
    symbol_name: Annotated[str | None, Query(description="Function or class name")] = None,
) -> Response:
    """
    1. Look up project by project_id (404 if not found).
    2. Validate file_path:
         - must not start with '/' or '\\'
         - must not contain '..' segments (after normalization)
         - 400 HTML fragment on violation
    3. Build CodeUnderstandingConfig from project.config.
    4. Call SymbolGenerator().explain_symbol(project_id, file_path, symbol_name, config, session)
    5. Render fragments/code_symbol_panel.html with:
         explanation_html=markdown_to_html(llm_response),
         file_path, symbol_name
    """
```

### 2. Router Registration — SKIP

`dashboard/app.py` already includes `code_router` (added by F-00046). Do NOT touch it.

### 3. Integration Tests — tests/integration/test_code_module_routes.py

Write integration tests using the FastAPI `TestClient` and the testcontainer-managed DB session. Mock external services (LanceDB, Ollama) but NOT the database. Use a **new file** (`test_code_module_routes.py`) — do NOT touch `tests/integration/test_code_index_pipeline.py` (F-00046's test file for the same router).

The endpoints return HTML fragments, so assertions check `resp.text` for expected markers (selectors, text, data attributes), not `resp.json()`.

```python
def test_list_modules_returns_404_when_no_level1_doc(client, test_project):
    resp = client.get(f"/api/projects/{test_project.id}/code/modules")
    assert resp.status_code == 404

def test_list_modules_returns_html_fragment(client, test_project, db_session):
    # Insert a Level 1 ProjectDoc with fixture content
    _insert_level1_doc(db_session, test_project.id, FIXTURE_LEVEL1_DOC)
    resp = client.get(f"/api/projects/{test_project.id}/code/modules")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "code-components-section" in resp.text  # container id
    assert "engine/" in resp.text                   # at least one parsed module path

def test_get_module_generates_and_renders_detail(client, test_project, db_session, mocker):
    mocker.patch(
        "dashboard.routers.code.ModuleGenerator.get_or_generate",
        return_value=(_fake_doc(), False),  # (doc, was_cached)
    )
    _insert_level1_doc(db_session, test_project.id, FIXTURE_LEVEL1_DOC)
    resp = client.get(f"/api/projects/{test_project.id}/code/modules/engine")
    assert resp.status_code == 200
    assert "freshly generated" in resp.text  # badge when was_cached=False

def test_get_module_returns_generating_fragment_on_timeout(client, test_project, db_session, mocker):
    async def slow_gen(*args, **kwargs):
        await asyncio.sleep(2)
        return (_fake_doc(), False)
    mocker.patch(
        "dashboard.routers.code.ModuleGenerator.get_or_generate",
        side_effect=slow_gen,
    )
    _insert_level1_doc(db_session, test_project.id, FIXTURE_LEVEL1_DOC)
    resp = client.get(f"/api/projects/{test_project.id}/code/modules/engine")
    assert resp.status_code == 200
    assert 'hx-trigger="load delay:2s"' in resp.text  # polling marker

def test_regenerate_module_skips_cache(client, test_project, db_session, mocker):
    get_or_gen = mocker.patch("dashboard.routers.code.ModuleGenerator.get_or_generate")
    gen_level2 = mocker.patch(
        "dashboard.routers.code.ModuleGenerator.generate_level2",
        return_value=_fake_doc(),
    )
    _insert_level1_doc(db_session, test_project.id, FIXTURE_LEVEL1_DOC)
    resp = client.post(f"/api/projects/{test_project.id}/code/modules/engine/generate")
    assert resp.status_code == 200
    get_or_gen.assert_not_called()
    gen_level2.assert_called_once()

def test_explain_symbol_returns_html_fragment(client, test_project, mocker):
    mocker.patch(
        "dashboard.routers.code.SymbolGenerator.explain_symbol",
        return_value="## RingBuffer\n\nFixed-capacity buffer.",
    )
    resp = client.get(
        f"/api/projects/{test_project.id}/code/symbol?file_path=engine/main.cpp"
    )
    assert resp.status_code == 200
    assert "symbol-panel-" in resp.text  # panel id prefix

def test_explain_symbol_rejects_path_traversal(client, test_project):
    resp = client.get(
        f"/api/projects/{test_project.id}/code/symbol?file_path=../../etc/passwd"
    )
    assert resp.status_code == 400

def test_explain_symbol_rejects_absolute_path(client, test_project):
    resp = client.get(
        f"/api/projects/{test_project.id}/code/symbol?file_path=/etc/passwd"
    )
    assert resp.status_code == 400

def test_explain_symbol_with_symbol_name(client, test_project, mocker):
    mocker.patch(
        "dashboard.routers.code.SymbolGenerator.explain_symbol",
        return_value="RingBuffer is a lock-free buffer.",
    )
    resp = client.get(
        f"/api/projects/{test_project.id}/code/symbol"
        f"?file_path=engine/buffer/ring.h&symbol_name=RingBuffer"
    )
    assert resp.status_code == 200
    assert "RingBuffer" in resp.text
```

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md` for:
- Routers are thin — no business logic in route handlers
- Use `Depends(get_db)` for DB session injection
- `JSONResponse` for JSON endpoints, HTML fragments for htmx endpoints
- No bare `except:` — catch specific exceptions
- Test fixtures come from `tests/conftest.py` — use `client`, `db_session`, `test_project`
- NEVER connect to live DB in tests
- All tests must be deterministic and isolated

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write `test_code_routes.py` first. Tests must fail because the router doesn't exist yet.
2. **GREEN**: Implement `dashboard/routers/code.py` and register the router to make tests pass.
3. **REFACTOR**: Clean up while keeping all tests green.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `uv run pytest tests/integration/test_code_module_routes.py -v` -- all new tests must pass
2. Run `uv run pytest tests/integration/test_code_index_pipeline.py -v` -- F-00046's tests must still pass (no regressions on the existing 5 endpoints)
3. Run `uv run pytest tests/unit/ -v` -- no regressions
4. Run `uv run ruff check dashboard/routers/code.py` and `uv run mypy dashboard/routers/code.py`
5. Do NOT report `tests_passed: true` unless ALL tests pass with zero failures

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "api-impl",
  "work_item": "F-00048",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/code.py",
    "tests/integration/test_code_module_routes.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
