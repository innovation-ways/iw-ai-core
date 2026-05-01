# I-00055_S03_Tests_prompt

**Work Item**: I-00055 -- Architecture Diagram renders twice on Code page; inline copy unreadable in dark mode
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state.
Read-only introspection (`docker ps`, `docker inspect`, `docker logs`) is allowed.
Testcontainers spun up by pytest fixtures are an explicit allowed exception.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00055 --json`.
- `ai-dev/active/I-00055/I-00055_Issue_Design.md`
- `ai-dev/active/I-00055/reports/I-00055_S01_Backend_report.md`
- `orch/rag/mapgen.py`
- `dashboard/routers/code_ui.py`
- Existing test patterns: `tests/CLAUDE.md`, `tests/conftest.py`, `tests/dashboard/conftest.py` (for the dashboard test fixtures)

## Output Files

- `ai-dev/active/I-00055/reports/I-00055_S03_Tests_report.md`
- `tests/unit/rag/test_mapgen.py` (new test cases — extend, do not duplicate)
- `tests/dashboard/test_code_page_arch_diagram.py` (new file)

## Context

You are writing the regression coverage for **I-00055**. The bug: the Code page renders the architecture mermaid diagram twice because `MapGenerator._assemble_markdown` embeds it in the architecture-map markdown AND the dashboard renders the standalone `diagram-architecture` doc separately.

The S01 fix has two parts: (a) `_assemble_markdown` no longer emits the diagram block, (b) a `strip_trailing_arch_diagram_section` helper applied at render time strips legacy content.

You must produce three test artifacts:

1. A **reproduction test** that would FAIL on pre-S01 code and PASS on the fixed code.
2. **Unit tests** for the strip helper covering positive, idempotent, and negative cases.
3. **Regression coverage** for the mapgen content invariant.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Tests must verify **specific values**, not just shape:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this incident specifically:

- BAD: `assert html.count("mermaid") > 0` — passes whether there's one or two diagrams.
- GOOD: `assert inline_count + bottom_count == 1` — proves exactly one diagram renders.
- BAD: `assert "## Architecture Diagram" not in md` only — doesn't catch the case where the H2 is absent but a stray ` ```mermaid ` fence remains.
- GOOD: assert all three forbidden substrings are absent: `## Architecture Diagram`, `<!-- purpose:`, ` ```mermaid `.

## Requirements

### 1. Unit tests for `MapGenerator._assemble_markdown` invariant

Add to `tests/unit/rag/test_mapgen.py` (create the directory and file if absent — match the path layout of similar `tests/unit/rag/test_*.py` files; if none exist, place them under the existing `tests/unit/` tree consistent with `tests/CLAUDE.md`).

```python
def test_i00055_assemble_markdown_omits_inline_diagram():
    """RED until I-00055 lands. The architecture-map content must contain
    no '## Architecture Diagram' H2, no purpose comment, and no mermaid fence."""
    g = MapGenerator(...minimal-required-args...)
    answers = {key: f"answer for {key}" for key, _, _ in MapGenerator.QUESTIONS}
    md = g._assemble_markdown(
        answers,
        mermaid="graph TD\n  A --> B",
        purpose="example purpose",
    )
    assert "## Architecture Diagram" not in md
    assert "<!-- purpose:" not in md
    assert "```mermaid" not in md
```

If `MapGenerator.__init__` requires non-trivial dependencies (config, project, etc.), reuse the fixtures already in `tests/unit/rag/` if any, or stub minimally. The test is a **string contract** — it should not need an LLM, embeddings, or DB.

### 2. Unit tests for `strip_trailing_arch_diagram_section`

Add three cases:

```python
def test_strip_trailing_arch_diagram_section_removes_legacy_block():
    legacy = (
        "# Architecture Map\n\n"
        "## Purpose\nA test project.\n\n"
        "## Architecture Diagram\n\n"
        "<!-- purpose: example -->\n\n"
        "```mermaid\n---\nconfig:\n  layout: elk\n---\n"
        "graph TD\n  A --> B\n```\n"
    )
    cleaned = strip_trailing_arch_diagram_section(legacy)
    assert "## Architecture Diagram" not in cleaned
    assert "```mermaid" not in cleaned
    assert "## Purpose" in cleaned  # prefix preserved


def test_strip_trailing_arch_diagram_section_is_idempotent():
    legacy = "# X\n\n## Architecture Diagram\n\n```mermaid\ngraph TD\nA-->B\n```\n"
    once = strip_trailing_arch_diagram_section(legacy)
    twice = strip_trailing_arch_diagram_section(once)
    assert once == twice


def test_strip_trailing_arch_diagram_section_no_op_when_absent():
    clean = "# Architecture Map\n\n## Purpose\nA test project.\n"
    assert strip_trailing_arch_diagram_section(clean) == clean
```

Optionally add one more case proving a *non-trailing* H2 of the same name is NOT removed (defensive — guards against future authoring patterns):

```python
def test_strip_trailing_arch_diagram_section_keeps_non_trailing_h2():
    md = (
        "# Architecture Map\n\n"
        "## Architecture Diagram\nNot the last section.\n\n"
        "## Purpose\nFinal section.\n"
    )
    assert strip_trailing_arch_diagram_section(md) == md
```

### 3. Dashboard reproduction test

Create `tests/dashboard/test_code_page_arch_diagram.py`. Use the existing dashboard test conventions (`tests/dashboard/conftest.py`, TestClient, project fixture, ProjectDoc seeding). Read `tests/CLAUDE.md` for required setup steps (FTS triggers after `Base.metadata.create_all()` etc.).

The test must:

1. Seed a project.
2. Seed an `architecture-map` ProjectDoc whose content **contains** the legacy trailing `## Architecture Diagram` + mermaid block (proves the strip helper is engaged).
3. Seed a `diagram-architecture` ProjectDoc with a clean DSL.
4. Seed a completed `CodeIndexJob` for that project pointing at the architecture-map doc id (so `code_page` finds the index status).
5. GET `/project/{project_id}/code` and assert:
   - `resp.status_code == 200`
   - `inline = resp.text.count('<pre data-lang="mermaid"')`
   - `bottom = resp.text.count('<div class="mermaid"')`
   - `assert inline + bottom == 1`

Use the project's existing TestClient + DB fixtures. Do NOT mock the database (`CLAUDE.md` rule).

### 4. Run the full local gate

```bash
make test-unit
make test-integration   # only if it currently passes on main; otherwise scope to changed paths
make lint && make typecheck
```

All MUST pass.

## Project Conventions

Read `tests/CLAUDE.md`. Critical rules:

- NEVER connect tests to the live DB (port 5433). Use testcontainers only.
- NEVER call `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- NEVER mock the DB in integration tests — FOR UPDATE locking can't be tested otherwise.
- MUST replace psycopg2 URLs in testcontainers: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- MUST run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in tests.
- `DaemonEvent.metadata` is named `event_metadata` in Python.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck
make lint
```

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00055",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/rag/test_mapgen.py",
    "tests/dashboard/test_code_page_arch_diagram.py"
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
