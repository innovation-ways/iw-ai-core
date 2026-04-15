# F-00048_S01_Backend_prompt

**Work Item**: F-00048 -- Code Understanding: Module + Symbol Views
**Step**: S01
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/F-00048/F-00048_Feature_Design.md` -- Design document
- `orch/rag/config.py` -- CodeUnderstandingConfig (from F-00045)
- `orch/rag/__init__.py` -- existing rag package (F-00045 created it; F-00046 populated it with `indexer.py`, `job.py`, `mapgen.py`)
- `orch/rag/mapgen.py` -- reference pattern for LanceDB connection, embedding, Ollama HTTP call. Match this pattern exactly; do NOT diverge.
- `orch/doc_service.py` -- DocService for ProjectDoc CRUD

## Output Files

- `orch/rag/module_gen.py` -- ModuleGenerator class
- `orch/rag/symbol_gen.py` -- SymbolGenerator class
- `orch/rag/parser.py` -- parse_modules_from_level1() utility
- `tests/unit/test_module_parser.py` -- unit tests for parser
- `tests/unit/test_module_gen.py` -- unit tests for ModuleGenerator
- `tests/integration/test_module_gen_integration.py` -- integration tests
- `ai-dev/work/F-00048/reports/F-00048_S01_Backend_report.md` -- Step report

## Context

You are implementing the backend layer for **F-00048: Code Understanding: Module + Symbol Views**.

Read the full design document at `ai-dev/active/F-00048/F-00048_Feature_Design.md` before writing any code. Read `CLAUDE.md` for project-specific conventions and hard rules. Read `dashboard/CLAUDE.md` for dashboard patterns.

This step implements three backend components:
1. `parse_modules_from_level1()` — pure function, parses markdown to extract module entries
2. `ModuleGenerator` — generates Level 2 module docs via LanceDB RAG + Ollama, cached as ProjectDoc
3. `SymbolGenerator` — generates Level 3 symbol explanations via direct file read + tree-sitter, never cached

## Requirements

### 1. orch/rag/parser.py — parse_modules_from_level1()

Implement a pure function (no I/O, no DB access) that takes a markdown string and returns a list of module entry dicts.

```python
def parse_modules_from_level1(doc_content: str) -> list[dict]:
    """
    Extract component entries from Level 1 architecture doc.

    Returns list of dicts with keys:
      - name: str       — human-readable module name (e.g. "C++ Sensor Engine")
      - path: str       — filesystem path (e.g. "engine/")
      - description: str — short description
      - slug: str       — URL-safe identifier (e.g. "engine")

    Returns empty list if no components section is found.
    Never raises — all parsing errors result in empty list or partial list.
    """
```

Parsing rules:
- Scan for a section header containing "component", "architecture", "module", or "structure" (case-insensitive)
- Within that section, look for lines matching the pattern: `- \`{path}/\` -- {description}` or `- \`{path}/\`: {description}` or `- **{name}** (\`{path}/\`): {description}`
- Also handle plain format: `- {path}/ -- {name}: {description}`
- Slug is derived from path: `path.strip('/').replace('/', '-').lower()`
- If a line provides a name separate from the path, use it; otherwise use the path as the name
- The function is tolerant — unknown formats are skipped, not raised as errors

### 2. orch/rag/module_gen.py — ModuleGenerator

```python
from orch.rag.config import CodeUnderstandingConfig
from orch.db.models import ProjectDoc
from sqlalchemy.ext.asyncio import AsyncSession

class ModuleGenerator:
    MODULE_QUESTIONS = [
        "What is the primary responsibility of the {module} component?",
        "What are the most important files in {module} and what does each do?",
        "What external components or services does {module} depend on?",
        "What design patterns or architectural approaches are used in {module}?",
        "What are the key entry points or public interfaces of {module}?",
    ]

    def _make_slug(self, project_id: str, module_path: str) -> str:
        """Returns f"{project_id}-module-{module_path.strip('/').replace('/', '-')}" """

    async def generate_level2(
        self,
        project_id: str,
        module_path: str,
        module_name: str,
        config: CodeUnderstandingConfig,
        session: AsyncSession,
    ) -> ProjectDoc:
        """
        1. Open LanceDB table at {IW_CORE_INDEX_PATH}/{project_id}/vectors/
        2. Query each MODULE_QUESTION, filtering by metadata.file_path.startswith(module_path)
        3. For each question, embed the question using config.resolved_embed_model()
        4. Retrieve top-k chunks (k=5) from LanceDB where file_path has module_path prefix
        5. Concatenate retrieved chunks as context, call Ollama LLM (config.resolved_llm_model())
        6. Assemble all 5 answers into a single markdown document
        7. Create or update ProjectDoc via DocService with correct fields (see design doc)
        8. Return the ProjectDoc
        """

    async def get_or_generate(
        self,
        project_id: str,
        module_path: str,
        module_name: str,
        config: CodeUnderstandingConfig,
        session: AsyncSession,
    ) -> tuple[ProjectDoc, bool]:
        """
        1. Compute slug = self._make_slug(project_id, module_path)
        2. Check DocService for existing ProjectDoc with that slug
        3. If found: return (doc, True)  # was_cached=True
        4. If not found: call generate_level2(), return (doc, False)  # was_cached=False
        """
```

ProjectDoc fields for Level 2 docs:
- `doc_type = "research"`
- `tier = "fully_automated"`
- `editorial_category = "technical"`
- `slug = f"{project_id}-module-{module_path.strip('/').replace('/', '-')}"`
- `title = f"Module: {module_name} ({module_path})"`
- `content` = assembled markdown (headings for each question + answers)
- `project_id` = the project_id argument

LanceDB filtering: use `where` clause on the LanceDB table query to filter rows where `file_path` starts with `module_path`. Check the existing `CodeIndexer`/`MapGenerator` code for how LanceDB is opened and queried — match that pattern exactly.

Ollama call: use `httpx.AsyncClient` to POST to `{config.ollama_url}/api/generate` with `model=config.resolved_llm_model()`. Match the existing Ollama call pattern in `MapGenerator`.

### 3. orch/rag/symbol_gen.py — SymbolGenerator

```python
import tree_sitter
from orch.rag.config import CodeUnderstandingConfig
from sqlalchemy.ext.asyncio import AsyncSession

class SymbolGenerator:
    async def explain_symbol(
        self,
        project_id: str,
        file_path: str,          # relative to project root
        symbol_name: str | None, # None = explain whole file
        config: CodeUnderstandingConfig,
        session: AsyncSession,
    ) -> str:
        """
        1. Resolve absolute path: {project.repo_path}/{file_path}
        2. Read file content from disk (aiofiles or pathlib.Path.read_text)
        3. If symbol_name is provided:
           a. Detect language from file extension
           b. Use tree-sitter to parse the file
           c. Walk the syntax tree to find the named function/class/method
           d. Extract the source text of that node
           e. If not found, fall back to full file content
        4. Build prompt: "Explain what {symbol_name or file_path} does:\n\n```\n{source}\n```"
        5. Call Ollama LLM via httpx POST to {config.ollama_url}/api/generate
        6. Return the LLM response as a markdown string
        Never creates or stores a ProjectDoc.
        """
```

tree-sitter usage:
- Use `tree_sitter` Python package (already installed by F-00046 CodeIndexer)
- Detect language from extension: `.py` → Python, `.cpp`/`.cc`/`.cxx` → C++, `.h`/`.hpp` → C++, `.js`/`.ts` → JavaScript/TypeScript, `.rs` → Rust, `.go` → Go
- For unknown extensions, skip tree-sitter and use full file content
- Symbol search: walk the tree looking for `function_definition`, `class_definition`, `function_item`, `impl_item`, `method_declaration` nodes whose `name` child matches `symbol_name`
- If tree-sitter parse fails for any reason, fall back to full file content — never raise

To get project repo_path: query `Project` model by `project_id`, use `project.repo_path` (or `project.path` — check the actual field name in `orch/db/models.py`).

### 4. Unit Tests

**tests/unit/test_module_parser.py** — TDD: write tests first, then implement.

```python
FIXTURE_LEVEL1_DOC = """
# Architecture Overview

## Components

- `engine/` -- C++ Sensor Engine: UDP listener and FFT pipeline
- `api/` -- Python FastAPI: REST backend and authentication
- `worker/` -- Celery: async background job processing
"""

def test_parse_returns_three_modules():
    modules = parse_modules_from_level1(FIXTURE_LEVEL1_DOC)
    assert len(modules) == 3

def test_parse_module_fields():
    modules = parse_modules_from_level1(FIXTURE_LEVEL1_DOC)
    engine = next(m for m in modules if m["path"] == "engine/")
    assert engine["name"] == "C++ Sensor Engine"
    assert engine["slug"] == "engine"
    assert "UDP" in engine["description"]

def test_parse_empty_doc_returns_empty_list():
    assert parse_modules_from_level1("") == []

def test_parse_no_components_section_returns_empty_list():
    assert parse_modules_from_level1("# Title\n\nSome content with no components.") == []

def test_parse_slug_with_nested_path():
    doc = "## Components\n\n- `src/engine/core/` -- Core: processing\n"
    modules = parse_modules_from_level1(doc)
    assert modules[0]["slug"] == "src-engine-core"

def test_parse_never_raises():
    # Malformed input must not raise
    result = parse_modules_from_level1("```\nnot valid markdown\n```\n\x00\xff")
    assert isinstance(result, list)
```

**tests/unit/test_module_gen.py** — mock DocService and LanceDB:

```python
def test_get_or_generate_cache_hit(mocker):
    """When ProjectDoc exists, get_or_generate returns it with was_cached=True"""
    mock_doc = ProjectDoc(slug="proj-module-engine", ...)
    mocker.patch("orch.rag.module_gen.DocService.get_by_slug", return_value=mock_doc)
    gen = ModuleGenerator()
    doc, was_cached = await gen.get_or_generate("proj", "engine/", "Engine", config, session)
    assert was_cached is True
    assert doc is mock_doc

def test_get_or_generate_cache_miss_calls_generate(mocker):
    """When ProjectDoc does not exist, get_or_generate calls generate_level2"""
    mocker.patch("orch.rag.module_gen.DocService.get_by_slug", return_value=None)
    mock_generate = mocker.patch.object(ModuleGenerator, "generate_level2", ...)
    gen = ModuleGenerator()
    doc, was_cached = await gen.get_or_generate(...)
    assert was_cached is False
    mock_generate.assert_called_once()

def test_make_slug():
    gen = ModuleGenerator()
    assert gen._make_slug("my-project", "engine/") == "my-project-module-engine"
    assert gen._make_slug("my-project", "src/engine/core/") == "my-project-module-src-engine-core"
```

### 5. Integration Tests

**tests/integration/test_module_gen_integration.py**:

```python
async def test_get_or_generate_creates_project_doc(db_session, test_project):
    """Full cycle: generate Level 2, confirm ProjectDoc saved in DB"""
    # Mock LanceDB + Ollama calls (they need live services)
    gen = ModuleGenerator()
    with patch("orch.rag.module_gen.lancedb.connect"), \
         patch("orch.rag.module_gen.httpx.AsyncClient.post", ...):
        doc, was_cached = await gen.get_or_generate(
            test_project.id, "engine/", "Engine", config, db_session
        )
    assert was_cached is False
    assert doc.slug == f"{test_project.id}-module-engine"
    assert doc.doc_type == "research"
    assert doc.tier == "fully_automated"

async def test_get_or_generate_returns_cached_on_second_call(db_session, test_project):
    """Second call returns same doc without regenerating"""
    gen = ModuleGenerator()
    with patch(...):
        doc1, _ = await gen.get_or_generate(...)
        doc2, was_cached = await gen.get_or_generate(...)
    assert was_cached is True
    assert doc1.id == doc2.id
```

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for:
- SQLAlchemy 2.0 async session patterns (`AsyncSession`)
- Test fixtures: `db_session`, `test_project` from `tests/conftest.py`
- NEVER connect to live DB in tests — testcontainers only
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` must run after `Base.metadata.create_all()`
- No mocking DB in integration tests — only mock external services (LanceDB file I/O, Ollama HTTP)
- Match existing import style from `orch/rag/` modules

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write all test files first. Run them — they must fail with ImportError or AttributeError.
2. **GREEN**: Implement `parser.py`, `module_gen.py`, `symbol_gen.py` to make tests pass.
3. **REFACTOR**: Clean up while keeping all tests green.

Do not skip the RED phase.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `uv run pytest tests/unit/ -v` — ALL unit tests must pass
2. Run `uv run pytest tests/integration/ -v -k test_module` — integration tests must pass
3. Run `uv run ruff check orch/rag/` and `uv run mypy orch/rag/`
4. Do NOT report `tests_passed: true` unless ALL tests pass with zero failures

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00048",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/rag/parser.py",
    "orch/rag/module_gen.py",
    "orch/rag/symbol_gen.py",
    "tests/unit/test_module_parser.py",
    "tests/unit/test_module_gen.py",
    "tests/integration/test_module_gen_integration.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
