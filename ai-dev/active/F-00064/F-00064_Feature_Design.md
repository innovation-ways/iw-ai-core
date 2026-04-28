# F-00064: Code mapping diagram generation pipeline — per-module and architecture diagrams stored as ProjectDocs

**Type**: Feature
**Priority**: High
**Created**: 2026-04-28
**Status**: Approved

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live DB (port 5433).
Your job is to WRITE the migration FILE only.

Allowed for agents:
  - `alembic revision --autogenerate -m "..."` (writes a file only)
  - `alembic history / current / show` (read-only)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

Extends the `CodeIndexJob` pipeline to generate and persist Mermaid component
diagrams as `ProjectDoc` records: one architecture-level diagram produced by
`mapgen.py` during Level 1 generation, and one per-module diagram produced by
`module_gen.py` during Level 2 generation. Also introduces `orch/diagram/`, a
new server-side rendering package that converts Mermaid/D2 DSL to SVG via
optional binaries (`mmdc`, `d2`) with graceful no-op fallback when binaries are
absent, and adds a `diagram` value to the `DocType` PostgreSQL enum via
migration.

## Project Context

Read `CLAUDE.md` (root) and `orch/CLAUDE.md` for architecture, ORM patterns,
migration rules, and hard constraints. Key rules: sync SQLAlchemy 2.0, never
mock the DB in integration tests, never apply migrations from agent context.

## Scope

### In Scope

- `DocType.diagram` enum value + Alembic migration extending the PostgreSQL `doc_type` enum
- `orch/diagram/__init__.py` — empty package marker
- `orch/diagram/render.py` — `render_mermaid(dsl)` and `render_d2(dsl)` returning `str | None`; never raises; logs WARNING if binary absent; 10 s subprocess timeout
- `orch/diagram/install.py` — `check_diagram_tools() -> dict[str, bool]` keyed `"mermaid"` and `"d2"`
- `orch/rag/mapgen.py` — ELK frontmatter in `_build_mermaid` prompt; store architecture diagram as `ProjectDoc(doc_id="diagram-architecture", doc_type=DocType.diagram)`
- `orch/rag/module_gen.py` — generate per-module diagram after Level 2 doc; store as `ProjectDoc(doc_id=f"diagram-module-{slug}", doc_type=DocType.diagram)`; failure is caught and logged, never propagated
- `ai-core.sh install` — non-blocking notices for missing `mmdc` / `d2` binaries
- Unit tests: `tests/unit/rag/test_diagram_render.py`, `tests/unit/rag/test_mapgen_mermaid.py`

### Out of Scope

- Frontend display of stored diagrams (F-00065)
- QA chat diagram interception (F-00066)
- D2 diagram generation in `module_gen.py` (Mermaid only for now)
- Pre-rendering to SVG at storage time (DSL stored; SVG rendered on demand)
- Any changes to `CodeIndexJob` DB schema or progress tracking

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `DocType.diagram` to Python enum + generate Alembic migration | — |
| S02 | code-review-impl | Review S01 migration + enum change | — |
| S03 | backend-impl | `orch/diagram/` package; update `mapgen.py`, `module_gen.py`; update `ai-core.sh` | — |
| S04 | code-review-impl | Review S03 backend changes | — |
| S05 | tests-impl | Unit tests for `render.py` and `mapgen.py` ELK prompt | — |
| S06 | code-review-impl | Review S05 tests | — |
| S07 | code-review-final-impl | Global review of S01+S03+S05 | — |
| S08 | qv-gate | lint — `make lint` | — |
| S09 | qv-gate | format — `make format-check` | — |
| S10 | qv-gate | typecheck — `make typecheck` | — |
| S11 | qv-gate | unit-tests — `make test-unit` | — |
| S12 | qv-gate | integration-tests — `make test-integration` | — |

### Database Changes

- **Modified enums**: `doc_type` PostgreSQL enum — add `diagram` value
- **Migration notes**: Use `ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'diagram'` — cannot be run inside a transaction; the migration must set `transactional = False` in Alembic (i.e. include `op.execute("ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'diagram'")` with `connection.execution_options(isolation_level="AUTOCOMMIT")` pattern, OR use a non-transactional migration via `alembic.op.execute` with autocommit=True flag in the `upgrade()` function — verify by looking at how previous enum migrations were done in `orch/db/migrations/versions/`)

### API Changes

- None (F-00065 adds the serving endpoints)

### Frontend Changes

- None (F-00065 adds the display)

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00064/F-00064_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00064/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00064/prompts/F-00064_S01_Database_prompt.md` | Prompt | S01: enum + migration |
| `ai-dev/active/F-00064/prompts/F-00064_S02_CodeReview_Database_prompt.md` | Prompt | S02: review S01 |
| `ai-dev/active/F-00064/prompts/F-00064_S03_Backend_prompt.md` | Prompt | S03: diagram package + mapgen + module_gen |
| `ai-dev/active/F-00064/prompts/F-00064_S04_CodeReview_Backend_prompt.md` | Prompt | S04: review S03 |
| `ai-dev/active/F-00064/prompts/F-00064_S05_Tests_prompt.md` | Prompt | S05: unit tests |
| `ai-dev/active/F-00064/prompts/F-00064_S06_CodeReview_Tests_prompt.md` | Prompt | S06: review S05 |
| `ai-dev/active/F-00064/prompts/F-00064_S07_CodeReview_Final_prompt.md` | Prompt | S07: global review |
| `orch/diagram/__init__.py` | New file | Package marker |
| `orch/diagram/render.py` | New file | Server-side DSL→SVG rendering |
| `orch/diagram/install.py` | New file | Binary availability check |
| `orch/db/migrations/versions/<rev>_add_diagram_doc_type.py` | New file | Alembic migration |
| `orch/rag/mapgen.py` | Modified | ELK prompt + diagram doc storage |
| `orch/rag/module_gen.py` | Modified | Per-module diagram generation + storage |
| `ai-core.sh` | Modified | mmdc/d2 binary notices in install step |
| `tests/unit/rag/test_diagram_render.py` | New file | render.py unit tests |
| `tests/unit/rag/test_mapgen_mermaid.py` | New file | ELK frontmatter assertion |

## Acceptance Criteria

### AC1: Architecture diagram stored during Level 1 generation

```
Given a project with a completed LanceDB code index
When `MapGenerator.generate_level1()` completes
Then `project_docs` contains a row with doc_id="diagram-architecture",
     doc_type="diagram", and content that is valid Mermaid DSL
     containing the string "layout: elk"
```

### AC2: Per-module diagram stored during Level 2 generation

```
Given a module "orch/rag/" has been indexed in LanceDB
When `ModuleGenerator.generate_level2()` completes
Then `project_docs` contains a row with doc_id starting with "diagram-module-"
     and content that is valid Mermaid DSL with ≤12 graph nodes
```

### AC3: render_mermaid returns None gracefully when binary missing

```
Given `mmdc` binary is not present on PATH or ~/.local/bin
When `render_mermaid(valid_dsl)` is called
Then the function returns None without raising any exception
     and a WARNING is written to the logger
```

### AC4: Module diagram failure does not affect module doc

```
Given the diagram LLM call raises an exception
When `generate_level2()` completes
Then the Level 2 ProjectDoc is saved with status=published
     and the exception is logged at WARNING level, not re-raised
```

### AC5: DocType.diagram usable in ORM

```
Given the migration has been applied
When a ProjectDoc is created with doc_type=DocType.diagram
Then the row is persisted and queryable without IntegrityError
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| mmdc not on PATH | `shutil.which("mmdc")` returns None | `render_mermaid()` returns `None`, logs WARNING |
| d2 not on PATH | `shutil.which("d2")` returns None | `render_d2()` returns `None`, logs WARNING |
| mmdc times out | subprocess exceeds 10 s | Returns `None`, logs WARNING with timeout detail |
| mmdc returns nonzero exit | invalid DSL | Returns `None`, logs WARNING with stderr |
| LLM returns no fenced block | diagram prompt returns prose only | `_build_mermaid_for_module` uses fallback `"graph TD\n  A[{module_name}]"` |
| Diagram doc already exists | Re-running Level 1 or Level 2 | `DocService.update_doc` overwrites; no duplicate rows |
| Module path with dots | e.g. `orch.rag` | Normalized to `orch/rag` before slug generation (already done in `module_gen.py`) |

## Invariants

1. `render_mermaid()` and `render_d2()` NEVER raise — they always return `str | None`.
2. A diagram generation failure in `module_gen.py` NEVER causes `generate_level2()` to raise.
3. All `ProjectDoc` records with `doc_type=DocType.diagram` store DSL in `content`, never rendered SVG.
4. The `diagram-architecture` doc is always upserted (never duplicated) using `DocService`.
5. `check_diagram_tools()` always returns a dict with exactly two keys: `"mermaid"` and `"d2"`.

## Dependencies

- **Depends on**: None
- **Blocks**: F-00065 (diagram display in code view), F-00066 (proactive diagram rendering in QA chat)

## TDD Approach

- **Unit tests** (`tests/unit/rag/test_diagram_render.py`):
  - Monkeypatch `shutil.which` to simulate missing binaries → assert `None` return, no exception
  - Monkeypatch `subprocess.run` to raise `subprocess.TimeoutExpired` → assert `None` return
  - Monkeypatch `subprocess.run` to return `CompletedProcess(returncode=1, stderr=b"bad syntax")` → assert `None` return
  - Call `check_diagram_tools()` with both binaries absent → assert `{"mermaid": False, "d2": False}`
- **Unit tests** (`tests/unit/rag/test_mapgen_mermaid.py`):
  - Monkeypatch `Ollama.complete` to return a fixed response → assert `_build_mermaid` result contains `"layout: elk"`
- **Integration tests**: Not required for this feature — diagram storage is exercised transitively by existing `CodeIndexJob` integration tests if they exist; new ones would require a live Ollama which is out of scope for CI.

## Notes

- Check existing enum migrations in `orch/db/migrations/versions/` before generating — some PostgreSQL `ALTER TYPE ADD VALUE` migrations must run outside a transaction. Match the pattern used there exactly.
- The `mmdc` binary from `@mermaid-js/mermaid-cli` requires a Puppeteer/Chromium install on first run. On WSL/headless Linux this needs `--no-sandbox` flag passed to mmdc. The `render_mermaid` implementation should pass `["mmdc", "--input", "-", "--output", "-", "--outputFormat", "svg", "--puppeteerConfig", '{"args":["--no-sandbox","--disable-setuid-sandbox"]}']` when invoking via subprocess with stdin=DSL.
- The `d2` binary renders via `d2 - --format svg` reading DSL from stdin and writing SVG to stdout.
- Do NOT add `mmdc` or `d2` to `pyproject.toml` — they are optional system-level tools, not Python packages.
- `orch/diagram/render.py` should expose a unified `render(dsl: str, dsl_type: str) -> str | None` convenience function in addition to the two typed functions, for use by F-00066.
