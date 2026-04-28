# F-00064_S05_Tests_prompt

**Work Item**: F-00064 — Code mapping diagram generation pipeline
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00064/F-00064_Feature_Design.md`
- `ai-dev/active/F-00064/reports/F-00064_S03_Backend_report.md`
- `orch/diagram/render.py`
- `orch/diagram/install.py`
- `orch/rag/mapgen.py`
- `tests/conftest.py`
- `tests/unit/` (existing unit test examples for convention)

## Output Files

- `ai-dev/active/F-00064/reports/F-00064_S05_Tests_report.md`
- `tests/unit/rag/test_diagram_render.py` (new)
- `tests/unit/rag/test_mapgen_mermaid.py` (new)

## Context

You are adding unit test coverage for **F-00064**. Read `tests/CLAUDE.md` for test conventions. Tests MUST NOT connect to the live DB (port 5433) — unit tests only here, no testcontainers needed.

## Requirements

### 1. `tests/unit/rag/test_diagram_render.py`

Test `orch.diagram.render` functions. Use `pytest` and `monkeypatch`. No real subprocess execution — mock everything.

**Tests to implement:**

#### `test_render_mermaid_binary_missing`
- Monkeypatch `shutil.which` to return `None`
- Monkeypatch `Path.exists` (or the specific expanduser path) to return `False` for the fallback `~/.local/bin/mmdc`
- Call `render_mermaid("graph TD\n  A --> B")`
- Assert return value is `None`
- Assert no exception was raised

#### `test_render_mermaid_subprocess_timeout`
- Monkeypatch `shutil.which` to return `/usr/bin/mmdc` (binary "present")
- Monkeypatch `subprocess.run` to raise `subprocess.TimeoutExpired(cmd="mmdc", timeout=10)`
- Call `render_mermaid("graph TD\n  A --> B")`
- Assert return value is `None`
- Assert no exception was raised

#### `test_render_mermaid_nonzero_exit`
- Monkeypatch `shutil.which` to return `/usr/bin/mmdc`
- Monkeypatch `subprocess.run` to return `MagicMock(returncode=1, stderr=b"bad syntax")`
- Call `render_mermaid("not valid mermaid")`
- Assert return value is `None`

#### `test_render_mermaid_success`
- Monkeypatch `shutil.which` to return `/usr/bin/mmdc`
- Monkeypatch `subprocess.run` to return `MagicMock(returncode=0, stdout=b"<svg>...</svg>")`
- Call `render_mermaid("graph TD\n  A --> B")`
- Assert return value is `"<svg>...</svg>"`

#### `test_render_d2_binary_missing`
- Monkeypatch `shutil.which` to return `None` for `"d2"`
- Assert `render_d2("A -> B")` returns `None` without raising

#### `test_render_dispatcher_unknown_type`
- Call `render("some dsl", "plantuml")` (unknown type)
- Assert returns `None` without raising

#### `test_check_diagram_tools_structure`
- Monkeypatch `shutil.which` to return `None` for all binaries
- Call `check_diagram_tools()`
- Assert result is a dict
- Assert result has exactly keys `"mermaid"` and `"d2"`
- Assert both values are `False`

#### `test_check_diagram_tools_both_present`
- Monkeypatch `shutil.which` to return `"/usr/bin/fake"` for both
- Call `check_diagram_tools()`
- Assert `{"mermaid": True, "d2": True}`

### 2. `tests/unit/rag/test_mapgen_mermaid.py`

Test `orch.rag.mapgen.MapGenerator._build_mermaid` ELK injection.

#### `test_elk_frontmatter_injected_when_llm_omits_it`
- Create a `MapGenerator()` instance
- Monkeypatch `Ollama` (or `orch.rag.mapgen.Ollama`) so that `complete()` returns a mock whose `.text` is:
  ```
  ```mermaid
  graph TD
    A[CLI] --> B[Daemon]
    B --> C[DB]
  ```
  ```
- Call `_build_mermaid("- **CLI**: command interface\n- **Daemon**: background runner", mock_config)`
  where `mock_config` is a minimal `CodeUnderstandingConfig` mock (just needs `resolved_llm_model()` and `ollama_url`)
- Assert the returned DSL contains `"layout: elk"`

#### `test_elk_frontmatter_not_duplicated_when_llm_includes_it`
- Same setup but LLM returns a response that already includes the ELK frontmatter
- Assert `"layout: elk"` appears exactly once in the returned DSL

#### `test_fallback_dsl_when_no_fenced_block`
- Monkeypatch LLM to return prose with no fenced block
- Assert returned DSL starts with `"graph TD"` (the fallback) or contains `"layout: elk"` (if fallback also gets frontmatter injected)
- Assert the function does not raise

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert result is None` without also asserting no exception was raised
- BAD: `assert "elk" in dsl` (substring only — doesn't prove the frontmatter is correctly formed)
- GOOD: `assert result is None` + the test passes (pytest itself proves no exception raised)
- GOOD: `assert dsl.count("layout: elk") == 1` (exact count, not just presence)
- GOOD: `assert result == "<svg>...</svg>"` (specific value from mock, not just non-None)

Each test must verify what actually matters for the invariant, not just structural shape.

---

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — must pass
2. `make typecheck` — zero errors on touched files
3. `make lint` — zero errors
4. `make test-unit` — ALL tests pass, zero failures

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "F-00064",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/rag/test_diagram_render.py",
    "tests/unit/rag/test_mapgen_mermaid.py"
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
