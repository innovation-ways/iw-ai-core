# F-00064_S03_Backend_prompt

**Work Item**: F-00064 — Code mapping diagram generation pipeline
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00064/F-00064_Feature_Design.md`
- `ai-dev/active/F-00064/reports/F-00064_S01_Database_report.md`
- `ai-dev/active/F-00064/reports/F-00064_S02_CodeReview_Database_report.md`
- `orch/rag/mapgen.py`
- `orch/rag/module_gen.py`
- `orch/diagram/` (create new)
- `ai-core.sh`

## Output Files

- `ai-dev/active/F-00064/reports/F-00064_S03_Backend_report.md`
- `orch/diagram/__init__.py` (new)
- `orch/diagram/render.py` (new)
- `orch/diagram/install.py` (new)
- `orch/rag/mapgen.py` (modified)
- `orch/rag/module_gen.py` (modified)
- `ai-core.sh` (modified)

## Context

You are implementing the backend for **F-00064: Code mapping diagram generation pipeline**.

Read `CLAUDE.md`, `orch/CLAUDE.md`, and the design document. The S01 migration added `DocType.diagram`. This step wires diagram generation into the code mapping pipeline.

## Requirements

### 1. Create `orch/diagram/__init__.py`

Empty file — just the package marker.

### 2. Create `orch/diagram/render.py`

Implement three public functions:

```python
def render_mermaid(dsl: str) -> str | None:
    """Render Mermaid DSL to SVG string. Returns None on any failure."""

def render_d2(dsl: str) -> str | None:
    """Render D2 DSL to SVG string. Returns None on any failure."""

def render(dsl: str, dsl_type: str) -> str | None:
    """Convenience dispatcher: dsl_type is 'mermaid' or 'd2'."""
```

**Implementation rules** (all are non-negotiable):

- Use `import shutil, subprocess, logging, tempfile, os` — no third-party deps
- Binary discovery: `shutil.which("mmdc")` and fallback `Path("~/.local/bin/mmdc").expanduser()` for Mermaid; `shutil.which("d2")` for D2
- If binary not found: log `logging.warning("mmdc binary not found — Mermaid server-side rendering unavailable")` and return `None`
- Subprocess invocation for Mermaid:
  ```
  mmdc --input - --output - --outputFormat svg
       --puppeteerConfig '{"args":["--no-sandbox","--disable-setuid-sandbox"]}'
  ```
  Pass DSL as `input=dsl.encode()` via stdin. Output is SVG bytes.
- Subprocess invocation for D2: `d2 - --format svg` reading stdin, writing SVG to stdout
- Timeout: `subprocess.run(..., timeout=10)` — on `TimeoutExpired` log WARNING and return `None`
- On nonzero returncode: log WARNING with stderr content and return `None`
- On any other exception: log WARNING and return `None`
- NEVER raise from these functions

### 3. Create `orch/diagram/install.py`

```python
def check_diagram_tools() -> dict[str, bool]:
    """Check availability of diagram rendering binaries."""
```

Returns `{"mermaid": bool, "d2": bool}`. Uses the same discovery logic as `render.py`. No side effects.

### 4. Update `orch/rag/mapgen.py`

**In `_build_mermaid`:**

Update the prompt to:
1. Require ELK YAML frontmatter at the start of the diagram:
   ```
   The diagram MUST start with this exact YAML frontmatter block:
   ---
   config:
     layout: elk
   ---
   ```
2. Bound node count: "Maximum 15 nodes. If the system has more components, group minor ones."
3. Keep the existing `graph TD` or `flowchart TD` instruction
4. Keep the existing "no prose, no explanation, fenced ```mermaid block only" instruction

Update `_build_mermaid` return: after extracting the DSL from the fenced block, prepend the ELK frontmatter if it's not already present (defensive):

```python
ELK_FRONTMATTER = "---\nconfig:\n  layout: elk\n---\n"
if "layout: elk" not in mermaid_dsl:
    mermaid_dsl = ELK_FRONTMATTER + mermaid_dsl
```

**In `generate_level1`:**

After `self._assemble_markdown(answers, mermaid)` produces the architecture map markdown, add diagram storage. The DSL is already in `mermaid` (the raw Mermaid string from `_build_mermaid`). Store it:

```python
# Store architecture diagram as a separate ProjectDoc
def store_arch_diagram(dsl: str) -> None:
    from orch.db.models import DocTier, DocType, EditorialCategory
    from orch.db.session import SessionLocal as DefaultSessionLocal
    factory = db_session_factory or DefaultSessionLocal
    with factory() as session:
        doc_service = DocService(session)
        existing = doc_service.get_doc(project_id, "diagram-architecture")
        kwargs = dict(
            project_id=project_id,
            doc_id="diagram-architecture",
            title=f"{project.display_name} — Architecture Diagram",
            doc_type=DocType.diagram,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            content=dsl,
            generated_by="code-understanding:mapgen",
            source_paths=["*"],
        )
        if existing is None:
            doc_service.create_doc(**kwargs)
        else:
            doc_service.update_doc(**{k: v for k, v in kwargs.items()
                                       if k not in ("project_id", "doc_id")},
                                   project_id=project_id, doc_id="diagram-architecture")
        session.commit()

try:
    await asyncio.to_thread(store_arch_diagram, mermaid)
except Exception as exc:
    import logging
    logging.warning("Architecture diagram storage failed for %s: %s", project_id, exc)
```

**CRITICAL**: The try/except around `asyncio.to_thread(store_arch_diagram, mermaid)` is NON-NEGOTIABLE. Diagram storage failure MUST NOT propagate to `generate_level1`. The doc generation flow must complete even if diagram persistence fails.

Check `DocService.create_doc` and `DocService.update_doc` signatures in `orch/doc_service.py` — match them exactly.

Note: `project` object is available in `generate_level1` from the `do_upsert` inner function. Restructure only as needed — keep the existing architecture intact.

### 5. Update `orch/rag/module_gen.py`

In `generate_level2`, after the module doc is successfully created/updated (after `DocService` commit), add diagram generation wrapped in a try/except:

```python
try:
    await self._generate_and_store_module_diagram(
        project_id=project_id,
        module_path=module_path,
        module_name=module_name,
        config=config,
        session=session,
        retrieved_nodes=nodes,   # pass nodes already retrieved for the module
    )
except Exception as exc:
    import logging
    logging.warning(
        "Module diagram generation failed for %s/%s: %s",
        project_id, module_path, exc
    )
```

Implement `_generate_and_store_module_diagram` as an async method:

```python
async def _generate_and_store_module_diagram(
    self,
    project_id: str,
    module_path: str,
    module_name: str,
    config: CodeUnderstandingConfig,
    session: Session,
    retrieved_nodes: list[Any],
) -> None:
```

- Build context string from `retrieved_nodes` (same pattern as `_build_context_str` in mapgen, or inline it)
- Prompt the LLM (use the same `Ollama` instance pattern as `generate_level2`):
  ```
  You are generating a Mermaid component diagram for the '{module_name}' module.
  
  Code context:
  {context_str}
  
  Rules:
  - Output ONLY a fenced ```mermaid block. No prose, no explanation.
  - The diagram MUST start with this YAML frontmatter:
    ---
    config:
      layout: elk
    ---
  - Use 'graph TD' direction.
  - Maximum 12 nodes. Group minor items if needed.
  - Node IDs: short alphanumeric (e.g., QA, IDX, CFG). Labels in [brackets].
  - Show the main internal components and their key dependencies.
  ```
- Extract DSL from fenced block using the same regex as `mapgen._build_mermaid`
- Fallback if no block found: `f"---\nconfig:\n  layout: elk\n---\ngraph TD\n  A[{module_name}]"`
- Ensure ELK frontmatter is present (same defensive check as in mapgen)
- Build `slug` using `self._make_slug(project_id, module_path)` (already exists)
- Store via `DocService`:
  ```python
  doc_id = f"diagram-module-{slug}"
  existing = doc_service.get_doc(project_id, doc_id)
  # create_doc or update_doc as in mapgen pattern
  ```
  `doc_type=DocType.diagram`, `tier=DocTier.fully_automated`, `editorial_category=EditorialCategory.technical`, `generated_by="code-understanding:module_gen"`

### 6. Update `ai-core.sh` — optional diagram tool notices

In the `install` section (after `uv sync`), add a check block:

```bash
echo ""
echo "Checking optional diagram tools..."
if ! command -v mmdc &>/dev/null && [ ! -f "$HOME/.local/bin/mmdc" ]; then
  echo -e "  \033[33m⚠ mmdc not found — Mermaid server-side rendering disabled.\033[0m"
  echo    "    To enable: npm install -g @mermaid-js/mermaid-cli"
else
  echo    "  ✓ mmdc available"
fi
if ! command -v d2 &>/dev/null; then
  echo -e "  \033[33m⚠ d2 not found — D2 diagram rendering disabled.\033[0m"
  echo    "    To enable: go install oss.terrastruct.com/d2@latest"
else
  echo    "  ✓ d2 available"
fi
```

This block must not affect exit code. Keep it clearly delimited by a comment.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — must pass with zero drift (or auto-fixed)
2. `make typecheck` — zero errors on touched files
3. `make lint` — zero errors

## TDD Requirement

Follow TDD (Red-Green-Refactor). Write the failing tests in `tests/unit/rag/test_diagram_render.py` first (minimal stubs), implement until green, then refactor.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00064",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/diagram/__init__.py",
    "orch/diagram/render.py",
    "orch/diagram/install.py",
    "orch/rag/mapgen.py",
    "orch/rag/module_gen.py",
    "ai-core.sh"
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
