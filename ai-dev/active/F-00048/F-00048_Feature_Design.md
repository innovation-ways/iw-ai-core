# F-00048: Code Understanding: Module + Symbol Views

**Type**: Feature
**Priority**: High
**Created**: 2026-04-15
**Status**: Approved

---

## Description

Adds drill-down navigation to the Code tab in the project dashboard. Module cards parsed from the Level 1 architecture doc let users navigate to Level 2 module detail views, generated on-demand via module-scoped RAG and cached as `ProjectDoc` sub-docs. Clicking a file or function within a module opens a Level 3 symbol explanation rendered inline (on-demand, not cached). Breadcrumb navigation connects all three levels.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key points:
- FastAPI + Jinja2 templates + htmx (no build step — Tailwind from CDN)
- Templates in `fragments/` must NOT extend `base.html`
- Routes are thin — business logic belongs in `orch/` layer
- `orch/rag/` package with `CodeUnderstandingConfig` (F-00045), `CodeIndexer` + `MapGenerator` + `CodeIndexJobRunner` (F-00046)
- `dashboard/routers/code.py` already exists and is registered in `dashboard/app.py` (created by F-00046 with 5 indexing/status endpoints). This feature **extends** that router — it does NOT create a new file or re-register the router.
- Code tab page + architecture fragment already exist (F-00047)
- `ProjectDoc` ORM and `DocService` for Level 2 caching
- LanceDB index at `{IW_CORE_INDEX_PATH}/{project_id}/vectors/`
- All tests use testcontainers — NEVER connect to live DB on port 5433

## Scope

### In Scope

- `orch/rag/module_gen.py` — `ModuleGenerator` class: Level 2 doc generation with LanceDB module-scoped retrieval, Ollama LLM, `ProjectDoc` caching
- `orch/rag/symbol_gen.py` — `SymbolGenerator` class: Level 3 symbol/file explanation via direct file read + tree-sitter extraction, not cached
- `orch/rag/parser.py` — `parse_modules_from_level1()` utility extracting module entries from Level 1 markdown
- `dashboard/routers/code.py` — add 4 new endpoints (modules list, module detail, module regeneration, symbol explanation) to the existing router created by F-00046. Do NOT create a new router or re-register it in `dashboard/app.py`.
- Frontend: module cards section in architecture view, Level 2 module detail view, Level 3 inline symbol panel, breadcrumb navigation across levels
- Unit tests for `parse_modules_from_level1()`, `get_or_generate()` cache hit/miss logic
- Integration tests for full Level 2 generation and caching flow

### Out of Scope

- Changes to `CodeIndexer`, `MapGenerator`, or Level 1 map generation (F-00046 scope)
- Changes to `CodeUnderstandingConfig` (F-00045 scope)
- Changes to the existing Code tab page, architecture fragment, or job status UI (F-00047 scope)
- Q&A / SSE streaming UI (F-00049 scope)
- Modifications to the existing 5 indexing/status endpoints in `dashboard/routers/code.py` (F-00046 scope)
- Any new database tables or Alembic migrations (uses existing `project_docs` table)

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `ModuleGenerator`, `SymbolGenerator`, `parse_modules_from_level1()` | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | api-impl | 4 API endpoints in `dashboard/routers/code.py` | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | frontend-impl | Module cards, Level 2 view, Level 3 inline panel, breadcrumb | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | code-review-final-impl | Final cross-agent review | — |
| S08 | qv-gate (lint) | `uv run ruff check .` | — |
| S09 | qv-gate (format) | `uv run ruff format --check .` | — |
| S10 | qv-gate (typecheck) | `uv run mypy orch/ dashboard/` | — |
| S11 | qv-gate (unit-tests) | `uv run pytest tests/unit/ -v` | — |
| S12 | qv-gate (integration-tests) | `uv run pytest tests/integration/ -v --alluredir=allure-results` | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None (uses existing `project_docs` table via `DocService`)
- **Migration notes**: No migration required. Level 2 docs are stored using existing `ProjectDoc` ORM with `doc_type="research"`, `tier="fully_automated"`, `editorial_category="technical"`.

### API Changes

- **New endpoints**:
  - `GET /api/projects/{project_id}/code/modules` — parsed module list from Level 1 doc
  - `GET /api/projects/{project_id}/code/modules/{module_slug}` — get or generate Level 2
  - `POST /api/projects/{project_id}/code/modules/{module_slug}/generate` — force regenerate Level 2
  - `GET /api/projects/{project_id}/code/symbol` — symbol explanation (query params: `file_path`, `symbol_name`)
- **Modified endpoints**: None

### Frontend Changes

- **New components**:
  - `templates/fragments/code_module_cards.html` — module cards grid htmx fragment
  - `templates/fragments/code_module_detail.html` — Level 2 module detail htmx fragment
  - `templates/fragments/code_symbol_panel.html` — Level 3 inline symbol explanation fragment
  - `templates/fragments/code_module_spinner.html` — loading state fragment
- **Modified components**:
  - Architecture view in Code tab (adds COMPONENTS section below Mermaid diagram)
  - Breadcrumb component to show current navigation level

## Backend Module: orch/rag/module_gen.py

```python
class ModuleGenerator:
    """
    Generates Level 2 module detail on demand, cached as ProjectDoc.
    """
    MODULE_QUESTIONS = [
        "What is the primary responsibility of the {module} component?",
        "What are the most important files in {module} and what does each do?",
        "What external components or services does {module} depend on?",
        "What design patterns or architectural approaches are used in {module}?",
        "What are the key entry points or public interfaces of {module}?",
    ]

    async def generate_level2(
        self,
        project_id: str,
        module_path: str,  # e.g. "engine/" or "api/"
        module_name: str,  # e.g. "C++ Sensor Engine" or "Python API"
        config: CodeUnderstandingConfig,
        session: AsyncSession,
    ) -> ProjectDoc:
        """
        1. Filter LanceDB index by file_path prefix matching module_path
        2. Run MODULE_QUESTIONS against filtered index via Ollama LLM
        3. Assemble into markdown doc
        4. Store as ProjectDoc with slug: f"{project_id}-module-{slugify(module_path)}"
        5. Return the ProjectDoc
        """
        ...

    async def get_or_generate(
        self,
        project_id: str,
        module_path: str,
        module_name: str,
        config: CodeUnderstandingConfig,
        session: AsyncSession,
    ) -> tuple[ProjectDoc, bool]:
        """Returns (doc, was_cached). Checks for existing ProjectDoc before generating."""
        ...
```

Level 2 `ProjectDoc` fields:
- `doc_type = "research"`
- `tier = "fully_automated"`
- `editorial_category = "technical"`
- Slug: `f"{project_id}-module-{module_path.strip('/').replace('/', '-')}"`
- `title`: `f"Module: {module_name} ({module_path})"`
- `content`: assembled markdown from the 5 MODULE_QUESTIONS answers

## Backend Module: orch/rag/symbol_gen.py

```python
class SymbolGenerator:
    """
    Generates Level 3 symbol (function/class) explanation on demand.
    NOT cached — always fresh.
    """
    async def explain_symbol(
        self,
        project_id: str,
        file_path: str,
        symbol_name: str | None,  # None = explain whole file
        config: CodeUnderstandingConfig,
        session: AsyncSession,
    ) -> str:
        """
        1. Read file content directly from repo (no RAG — targeted read)
        2. Extract symbol if symbol_name provided (use tree-sitter)
        3. Ask LLM: "Explain what {symbol_name} does in {file_path}: {source_code}"
        4. Return markdown explanation string (not stored as ProjectDoc)
        """
        ...
```

## Backend Utility: orch/rag/parser.py

```python
def parse_modules_from_level1(doc_content: str) -> list[dict]:
    """
    Extract component entries from Level 1 doc.
    Returns list of: {"name": str, "path": str, "description": str}
    Looks for lines matching: "- `{path}/` -- {description}" or similar patterns.
    """
```

The parser scans the Level 1 markdown for a "Components" or "Architecture" section and extracts structured entries. It is tolerant of formatting variations (backtick paths, plain paths, with or without trailing slash).

## API Endpoints: dashboard/routers/code.py

All four endpoints return **HTML fragments** via `templates.TemplateResponse(...)` (the same pattern F-00047 uses for `code_architecture_view.html`). They are called directly by htmx and the response HTML is inserted into the DOM by `hx-swap`. Markdown-to-HTML conversion happens in the router (not in the template) using the same `markdown` Python package already used elsewhere in the dashboard — if no existing converter is found, add one to `orch/doc_service.py` as a helper and reuse it across fragments.

Returning raw markdown with `| safe` in the template would be an XSS risk and would not render correctly; the server must convert to sanitized HTML before rendering.

### GET /api/projects/{project_id}/code/modules

Returns the parsed module list, rendered into `fragments/code_module_cards.html`.

- Looks up the project's Level 1 `ProjectDoc` (slug pattern from F-00046's `MapGenerator` — check the actual slug format in the merged code, do not hardcode).
- If not found → `404` with an inline error fragment (`fragments/code_empty_state.html` or similar — match F-00047's empty-state pattern).
- Otherwise: parses modules via `parse_modules_from_level1(doc.content)` and renders `fragments/code_module_cards.html` with `{modules, project_id, source_doc_slug}`.

### GET /api/projects/{project_id}/code/modules/{module_slug}

Gets or generates Level 2 for the given module slug and renders `fragments/code_module_detail.html`.

Template context:
- `project_id: str`
- `module: dict` (the parsed entry)
- `doc_html: str | None` — server-side-rendered HTML from `doc.content` markdown; `None` while still generating
- `was_cached: bool`
- `generating: bool`

Flow:
1. Look up Level 1 doc, parse modules, find entry for `module_slug`. `404` if not found.
2. Build `CodeUnderstandingConfig` from `project.config`.
3. Kick off generation via `asyncio.create_task(...)` + `asyncio.wait_for(asyncio.shield(task), timeout=0.5)` so the task keeps running if the wait times out (see S03 prompt for exact pattern).
4. On success within 500ms: render fragment with `generating=False`, `doc_html=markdown_to_html(doc.content)`.
5. On timeout: render fragment with `generating=True`, `doc_html=None`. The template includes `hx-trigger="load delay:2s"` to poll this same endpoint, which will hit the cache once the background task finishes writing the `ProjectDoc`.

Returns `404` if no Level 1 doc exists, or if `module_slug` is not in the parsed module list.

### POST /api/projects/{project_id}/code/modules/{module_slug}/generate

Force regenerates Level 2, ignoring any cached `ProjectDoc`. Same template + context as the GET above but `was_cached` is always `False`. Flow:
1. Look up Level 1 doc, parse modules, find entry. `404` if not found.
2. Delete any existing `ProjectDoc` with the module slug via `DocService.delete_by_slug(...)` (or equivalent — verify the exact helper name in `orch/doc_service.py`).
3. Call `ModuleGenerator().generate_level2(...)` directly (skips the cache-check branch of `get_or_generate`).
4. Render the same fragment as GET with `was_cached=False`.

### GET /api/projects/{project_id}/code/symbol

Query params: `file_path` (required), `symbol_name` (optional).

Validates `file_path` against path traversal (must not start with `/` and must not contain `..` segments). `400` on invalid input. `404` if project not found. Calls `SymbolGenerator().explain_symbol(...)` and renders `fragments/code_symbol_panel.html` with `{explanation_html, file_path, symbol_name}`. `explanation_html` is the server-side-rendered HTML from the LLM's markdown response.

### Content-negotiation note

htmx requests carry an `HX-Request: true` header. If a client calls these endpoints without that header (e.g., curl or a JSON consumer), the router MAY still return HTML — there is no separate JSON variant in this feature. Consumers that want JSON should use the 5 existing indexing/status endpoints created by F-00046, which are JSON.

## UI Design

### Module Cards (in Architecture view, below Mermaid)

Loaded via htmx after Level 1 renders (`hx-get="/api/.../code/modules"`). Displayed as a responsive card grid:

```
┌─────────────────────────────────────────────────────────┐
│ COMPONENTS                                              │
│                                                         │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │
│ │ engine/      │ │ api/         │ │ worker/      │     │
│ │ C++ Sensor   │ │ Python       │ │ Celery async │     │
│ │ Engine       │ │ FastAPI      │ │ workers      │     │
│ │              │ │ backend      │ │              │     │
│ │    [→ View]  │ │    [→ View]  │ │    [→ View]  │     │
│ └──────────────┘ └──────────────┘ └──────────────┘     │
└─────────────────────────────────────────────────────────┘
```

Each card's "View" button triggers `hx-get` to the module detail endpoint, replacing the main content area and updating the breadcrumb.

### Level 2 Module View

```
Architecture > engine/                    [↻ Regenerate]
────────────────────────────────────────────────────────
C++ Sensor Ingestion Engine
────────────────────────────────────────────────────────
{narrative description}

Key Files:
  engine/main.cpp           Entry point, UDP listener loop    [explain]
  engine/buffer/ring.h      Lock-free ring buffer             [explain]
  engine/pipeline/fft.cpp   FFT processing (AVX2)             [explain]

Dependencies: → Redis (outbound), ← UDP socket (inbound)
Patterns: producer-consumer, SIMD batch processing
```

### Level 3 Symbol View (inline, below file list)

```
engine/buffer/ring.h  [explain] → clicked

  ┌─────────────────────────────────────────────────────┐
  │ RingBuffer<T>                                       │
  │                                                     │
  │ Fixed-capacity, lock-free circular buffer using     │
  │ two atomic indices (head, tail) with cache-line     │
  │ padding to prevent false sharing...                 │
  │                                [✕ close]           │
  └─────────────────────────────────────────────────────┘
```

Each [explain] button appends the inline panel below its file row via `hx-swap="afterend"`. The close button removes the panel via `hx-delete` or JS `remove()`.

### Breadcrumb

```
Architecture > engine/ > ring.h
```

Each segment is a clickable htmx link that restores the appropriate view level.

## File Manifest

### Design package (lives under `ai-dev/active/F-00048/`)

| File | Type | Purpose |
|------|------|---------|
| `F-00048_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00048_S01_Backend_prompt.md` | Prompt | S01: ModuleGenerator + SymbolGenerator + parser |
| `prompts/F-00048_S02_CodeReview_prompt.md` | Prompt | S02: Review S01 |
| `prompts/F-00048_S03_API_prompt.md` | Prompt | S03: API endpoints |
| `prompts/F-00048_S04_CodeReview_prompt.md` | Prompt | S04: Review S03 |
| `prompts/F-00048_S05_Frontend_prompt.md` | Prompt | S05: Frontend components |
| `prompts/F-00048_S06_CodeReview_prompt.md` | Prompt | S06: Review S05 |
| `prompts/F-00048_S07_CodeReview_Final_prompt.md` | Prompt | S07: Final cross-agent review |

### Implementation files (touched by S01/S03/S05)

| File | Action | Agent | Purpose |
|------|--------|-------|---------|
| `orch/rag/parser.py` | **Create** | S01 backend-impl | `parse_modules_from_level1()` pure function |
| `orch/rag/module_gen.py` | **Create** | S01 backend-impl | `ModuleGenerator` class |
| `orch/rag/symbol_gen.py` | **Create** | S01 backend-impl | `SymbolGenerator` class |
| `tests/unit/test_module_parser.py` | **Create** | S01 backend-impl | Parser unit tests |
| `tests/unit/test_module_gen.py` | **Create** | S01 backend-impl | ModuleGenerator unit tests |
| `tests/integration/test_module_gen_integration.py` | **Create** | S01 backend-impl | Generator integration tests |
| `dashboard/routers/code.py` | **Modify** (extend existing F-00046 router) | S03 api-impl | Add 4 new endpoints to existing router; do NOT create new file or re-register |
| `tests/integration/test_code_module_routes.py` | **Create** | S03 api-impl | Route integration tests (separate from F-00046's `test_code_index_pipeline.py`) |
| `dashboard/templates/fragments/code_module_cards.html` | **Create** | S05 frontend-impl | Module cards grid fragment |
| `dashboard/templates/fragments/code_module_detail.html` | **Create** | S05 frontend-impl | Level 2 module detail fragment |
| `dashboard/templates/fragments/code_symbol_panel.html` | **Create** | S05 frontend-impl | Level 3 inline symbol panel |
| `dashboard/templates/fragments/code_module_spinner.html` | **Create** | S05 frontend-impl | Loading spinner fragment |
| `dashboard/templates/fragments/code_architecture_view.html` | **Modify** (extend F-00047 fragment) | S05 frontend-impl | Inject `#code-components-section` container + detail panel below Mermaid |

**Explicitly NOT modified** (do not touch):
- `dashboard/app.py` — router already registered by F-00046
- The 5 existing endpoints in `dashboard/routers/code.py` (F-00046 scope)
- `orch/db/models.py` / Alembic migrations — no schema changes
- F-00047's `project_code.html` page template (modifications stay inside the architecture fragment)

Reports are created during execution in `ai-dev/work/F-00048/reports/`.

## Acceptance Criteria

### AC1: Module list parsed from Level 1 doc

```
Given a Level 1 ProjectDoc with a components section listing "engine/" and "api/"
When GET /api/projects/{project_id}/code/modules is called
Then an HTML fragment of fragments/code_module_cards.html is returned
 And the fragment contains cards for both "engine/" and "api/"
 And each card shows name, path, and description
```

### AC2: Level 2 doc generated and cached on first request

```
Given no Level 2 ProjectDoc exists for module "engine/"
When GET /api/projects/{project_id}/code/modules/engine is called
Then ModuleGenerator.generate_level2() is called
 And a new ProjectDoc is created with the expected slug
 And the HTML fragment shows a "freshly generated" badge (was_cached=False)
```

### AC3: Level 2 doc returned from cache on subsequent request

```
Given a Level 2 ProjectDoc already exists for module "engine/"
When GET /api/projects/{project_id}/code/modules/engine is called again
Then no new generation occurs
 And the HTML fragment shows a "cached" badge (was_cached=True)
```

### AC4: Force regeneration invalidates cache

```
Given a cached Level 2 ProjectDoc for module "engine/"
When POST /api/projects/{project_id}/code/modules/engine/generate is called
Then the existing ProjectDoc is deleted and a new one generated
 And ModuleGenerator.get_or_generate() is NOT called (generate_level2 is called directly)
 And the HTML fragment shows the "freshly generated" badge
```

### AC5: Symbol explanation returned (whole file)

```
Given a valid file_path in the project repo
When GET /api/projects/{project_id}/code/symbol?file_path=engine/main.cpp is called
Then an HTML fragment of fragments/code_symbol_panel.html is returned
 And the explanation is rendered as HTML (from markdown)
 And no ProjectDoc is created
```

### AC6: Symbol explanation returned (named symbol)

```
Given a valid file_path and symbol_name in the project repo
When GET /api/projects/{project_id}/code/symbol?file_path=engine/buffer/ring.h&symbol_name=RingBuffer is called
Then an HTML fragment is returned whose header shows "RingBuffer"
```

### AC9: Path traversal rejected

```
Given a malicious file_path containing ".." or starting with "/"
When GET /api/projects/{project_id}/code/symbol?file_path=../../etc/passwd is called
Then the endpoint returns 400 and does NOT read any file from disk
```

### AC7: Module cards render in UI

```
Given a project with a Level 1 code architecture doc
When the Code tab is opened and the Architecture view loads
Then module cards appear below the Mermaid diagram
 And each card shows module name, path, and description
```

### AC8: Level 3 inline panel opens and closes

```
Given a Level 2 module view with file rows visible
When the [explain] button for a file row is clicked
Then an inline explanation panel appears below that row
When the [x close] button is clicked
Then the panel is removed from the DOM
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| No Level 1 doc | Project has no code architecture doc | GET /modules returns 404 |
| Empty module list | Level 1 doc has no component entries | GET /modules returns `{"modules": []}` |
| Unknown module_slug | Slug not in parsed module list | GET /modules/{slug} returns 404 |
| symbol_name not found in file | tree-sitter can't locate symbol | Explain whole file as fallback |
| File not in repo | file_path doesn't exist on disk | Return 404 with clear error message |
| Generation > 500ms | Ollama slow to respond | Return `{"generating": true}`, client polls |
| Concurrent regenerate requests | Two POSTs to /generate simultaneously | Second request waits for first; idempotent result |
| Module path with nested slashes | `module_path = "src/engine/core/"` | Slug: `src-engine-core`; file filter uses prefix match |

## Invariants

1. `get_or_generate()` is idempotent in the **sequential** case — calling it twice sequentially with the same args produces one `ProjectDoc`, not two.
2. `SymbolGenerator.explain_symbol()` never creates a `ProjectDoc` — it always returns a plain string.
3. The Level 2 `ProjectDoc` slug always has the form `{project_id}-module-{sanitized_path}`.
4. `parse_modules_from_level1()` never raises — returns an empty list if no components are found.
5. All 4 new endpoints are added to the existing router (prefix `/api/projects/{project_id}/code/`) created by F-00046; no new router is instantiated and `dashboard/app.py` is not touched.
6. No raw SQL — all DB access goes through SQLAlchemy ORM and `DocService`.

### Concurrency Note (not a strict invariant)

There is **no unique constraint** on `project_docs.slug` in the current schema (see `orch/db/models.py`). Two concurrent calls to `get_or_generate()` for the same module can both miss the cache check and produce two `ProjectDoc` rows with the same slug. This is acceptable for this feature because:

- Module generation is user-triggered from the UI — realistic concurrency is 1 user, 1 click.
- The `DocService.get_by_slug(...)` helper returns the newest matching row, so subsequent reads remain coherent.
- Adding a unique constraint is out of scope (would require a migration and would break F-00046's own `ProjectDoc` writes if they also lack slug uniqueness).

If duplicate rows become a problem in practice, a follow-up incident should add `UniqueConstraint("project_id", "slug")` on `ProjectDoc`. The design does not attempt to guarantee cross-process atomicity.

## Dependencies

- **Depends on**: F-00045 (`CodeUnderstandingConfig`), F-00046 (`dashboard/routers/code.py`, `MapGenerator` that produces the Level 1 `ProjectDoc`, LanceDB index under `{IW_CORE_INDEX_PATH}/{project_id}/vectors/`), F-00047 (Code tab page + architecture fragment — this feature adds content to the existing fragment)
- **Blocks**: None (parallel with F-00049)

## TDD Approach

- **Unit tests** (`tests/unit/test_module_parser.py`):
  - `parse_modules_from_level1()` with fixture markdown containing components
  - `parse_modules_from_level1()` with empty doc returns `[]`
  - `parse_modules_from_level1()` with no components section returns `[]`
  - Slug generation from various path formats (`engine/`, `src/engine/core/`)

- **Unit tests** (`tests/unit/test_module_gen.py`):
  - `get_or_generate()` cache hit path (mock `DocService.get_by_slug`)
  - `get_or_generate()` cache miss path (mock generation)
  - `generate_level2()` assembles markdown from question answers
  - Slug construction with special characters in path

- **Integration tests** (`tests/integration/test_module_gen_integration.py`):
  - Full generate + cache cycle against test DB
  - `ProjectDoc` created with correct fields
  - Second call to `get_or_generate()` returns same doc

- **Integration tests** (`tests/integration/test_code_routes.py`):
  - GET /modules returns 404 when no Level 1 doc exists
  - GET /modules/{slug} triggers generation and returns doc
  - GET /symbol returns explanation string

## Notes

- tree-sitter is already available via `tree-sitter` Python package — no new dependencies needed.
- The 500ms polling threshold for Level 2 generation is a frontend concern only — the backend always blocks until done. The frontend applies the timeout via `hx-trigger="load delay:500ms"` polling pattern.
- Level 2 docs are stored using `DocService` (existing service from F-00047). The `ModuleGenerator` must import and use `DocService`, not write raw ORM queries.
- The `parse_modules_from_level1()` function must be pure (no I/O, no DB) — it only processes the markdown string passed to it.
- For symbol extraction, tree-sitter language packs must already be installed by F-00046's `CodeIndexer`. Do not add new install steps.
