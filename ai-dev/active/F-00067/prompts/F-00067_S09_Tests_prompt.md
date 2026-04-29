# F-00067_S09_Tests_prompt

**Work Item**: F-00067 — Documentation Visual Design Overhaul
**Step**: S09
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00067/F-00067_Feature_Design.md` — Design doc (§Boundary Behavior, §Invariants, §TDD Approach)
- `ai-dev/active/F-00067/reports/F-00067_S01_Backend_report.md`
- `ai-dev/active/F-00067/reports/F-00067_S02_Frontend_report.md`
- `ai-dev/active/F-00067/reports/F-00067_S07_Backend_IndexPage_report.md`
- `orch/rag/mapgen.py`, `orch/rag/module_gen.py`, `orch/rag/index_gen.py`
- `tests/conftest.py` — Test fixtures and patterns
- `tests/CLAUDE.md` — Test organization rules

## Output Files

- `tests/unit/test_rag_mapgen_diagram.py` — New or extended
- `tests/unit/test_rag_module_gen_diagram.py` — New or extended
- `tests/unit/test_rag_index_gen.py` — New
- `tests/integration/test_rag_index_gen_integration.py` — New
- `ai-dev/active/F-00067/reports/F-00067_S09_Tests_report.md`

---

## Context

This step adds supplementary test coverage for the diagram prompt enhancements, the index page generator, and the boundary behaviors defined in the design doc. Some tests may already have been written by S01 and S07 — extend rather than duplicate.

---

## Requirements

### 1. Diagram prompt tests (`tests/unit/test_rag_mapgen_diagram.py`)

Test `MapGenerator._build_mermaid()`:

```python
def test_build_mermaid_includes_classdef():
    """classDef color palette is always injected into the prompt."""
    # Mock Ollama to return a minimal mermaid block
    # Assert returned DSL contains "classDef api"

def test_build_mermaid_returns_purpose():
    """Returns tuple (dsl, purpose) when LLM includes a purpose block."""
    # Mock Ollama to return both ```mermaid``` and ```purpose``` blocks
    # Assert tuple[0] is DSL, tuple[1] is the purpose string

def test_build_mermaid_purpose_fallback():
    """Falls back to default purpose when LLM omits purpose block."""
    # Mock Ollama to return only a ```mermaid``` block
    # Assert tuple[1] is the fallback string

def test_stored_content_format():
    """Stored content starts with <!-- purpose: --> comment before DSL."""
    # Assert content matches r"<!-- purpose: .+ -->\n---\nconfig:"
```

### 2. Module diagram prompt tests (`tests/unit/test_rag_module_gen_diagram.py`)

```python
def test_module_diagram_uses_lr_direction():
    """Module diagram prompt specifies LR direction."""
    # Capture the prompt string passed to LLM
    # Assert "graph LR" appears in the prompt or instructions

def test_module_diagram_classdef_in_prompt():
    """classDef palette instruction is in the module diagram prompt."""
    # Assert prompt contains "classDef api"

def test_module_diagram_structural_only_instruction():
    """Prompt instructs LLM to exclude DTOs, utilities, config."""
    # Assert prompt contains "Do NOT show" and "utility classes"
```

### 3. Index page generator tests (`tests/unit/test_rag_index_gen.py`)

```python
def test_generate_index_empty_project():
    """Empty project generates index with 'No documentation' note."""

def test_generate_index_groups_by_doc_type():
    """Index groups module docs under ## Module Documentation."""

def test_generate_index_calls_create_doc_first_time():
    """First call creates a new code-index doc."""

def test_generate_index_calls_update_doc_on_rerun():
    """Subsequent call updates existing code-index doc."""

def test_generate_index_first_sentence_extraction():
    """Description extracted from first non-header sentence of content."""

def test_generate_index_none_content_safe():
    """Doc with None content renders '—' as description."""
```

### 4. Integration test (`tests/integration/test_rag_index_gen_integration.py`)

```python
def test_index_page_created_in_db(db_session, test_project):
    """generate_index_page() creates a code-index ProjectDoc in the DB."""
    # Create test_project with 3 ProjectDocs of different types
    # Call generate_index_page(project_id, session)
    # Query DB for doc_id="code-index"
    # Assert doc.doc_type == DocType.architecture
    # Assert doc.tier == DocTier.fully_automated
    # Assert "## Module Documentation" in doc.content
```

Use testcontainer fixtures from `tests/conftest.py`. Read `tests/CLAUDE.md` for patterns. **NEVER** connect to the live DB on port 5433.

### 5. Boundary behavior tests

Cover every row in the design doc §Boundary Behavior table:

- `test_diagram_empty_components_fallback` — LLM returns empty → fallback diagram renders without crash
- `test_toc_skipped_for_few_headings` — If testing TOC logic server-side; otherwise note as covered by frontend tests
- `test_callout_unknown_type_fallback` — If testing callout parsing server-side
- `test_index_missing_purpose_marker` — Old diagram doc without `<!-- purpose:` → no KeyError/AttributeError

---

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Tests that only check output *shape* (non-empty, has a key, is a string) can pass even when the behavior is wrong. Every assertion in this step must check **specific values**:

- BAD: `assert result is not None`
- BAD: `assert "classDef" in dsl` (only checks that any classDef is present)
- GOOD: `assert "classDef api fill:#DBEAFE" in dsl` (verifies the specific canonical hex value)
- GOOD: `assert content.startswith("<!-- purpose:")` (verifies the exact format)
- GOOD: `assert doc.doc_type == DocType.architecture` (verifies the specific enum value, not just that `doc_type` exists)

If a test passes whether the bug is present or not, it is not a useful test.

## Project Conventions

Read `tests/CLAUDE.md`. Key rules:
- NEVER use live DB (port 5433)
- Use `monkeypatch.delenv()` not `importlib.reload()`
- Run `FTS_FUNCTION_SQL + FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in integration tests

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit`
5. `make test-integration` (for integration tests)

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "tests-impl",
  "work_item": "F-00067",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_rag_mapgen_diagram.py",
    "tests/unit/test_rag_module_gen_diagram.py",
    "tests/unit/test_rag_index_gen.py",
    "tests/integration/test_rag_index_gen_integration.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
