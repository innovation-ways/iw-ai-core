# F-00067_S01_Backend_prompt

**Work Item**: F-00067 — Documentation Visual Design Overhaul
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ No live DB migrations

No schema changes required for this step.

---

## Input Files

- `ai-dev/active/F-00067/F-00067_Feature_Design.md` — Design document (canonical color palette in §Semantic Color Palette section)
- `orch/rag/mapgen.py` — Architecture diagram generator (`_build_mermaid()` at line ~268)
- `orch/rag/module_gen.py` — Module diagram generator (`_generate_and_store_module_diagram()` at line ~231)

## Output Files

- `orch/rag/mapgen.py` — Modified
- `orch/rag/module_gen.py` — Modified
- `ai-dev/active/F-00067/reports/F-00067_S01_Backend_report.md` — Step report

---

## Context

You are enhancing the LLM prompts used to generate Mermaid diagrams for the code map feature. The current diagrams are flat black-and-white graphs with no color, no abstraction-level discipline, and no descriptive context. Your job is to improve the prompts so that generated diagrams are semantic, readable, and self-documenting.

**No new modules, no new DB tables, no API changes.** Only `mapgen.py` and `module_gen.py` are changed.

---

## Requirements

### 1. Semantic color palette via `classDef` in architecture diagram prompt (`mapgen.py`)

Locate `_build_mermaid()` in `orch/rag/mapgen.py`. Enhance the LLM prompt string to include the following instructions:

**Add this exact classDef block to the instructions:**
```
After the graph declaration, add this classDef block verbatim:
  classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F
  classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46
  classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F
  classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151
  classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764
  classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D
```

**Add class assignment instructions:**
- API/CLI entry points and routers → `class NodeID api`
- Database models, repositories, data stores → `class NodeID data`
- Background jobs, daemon, pipeline workers → `class NodeID worker`
- External APIs, third-party services → `class NodeID external`
- Dashboard/UI components → `class NodeID ui`
- Core orchestration services → `class NodeID core`

**Add abstraction-level instruction:**
```
Show only high-level architectural components (services, entry points, data stores, workers).
Do NOT include: utility classes, helper functions, DTOs, configuration classes, or import details.
Every node must be at the same abstraction level — no mixing services with low-level utilities.
```

**Add "Why" instruction:**
```
After the diagram block, output a second fenced block:
```purpose
[One or two sentences describing what this diagram shows and when a developer should refer to it.]
```
```

### 2. Extract and store the "Why" purpose paragraph (`mapgen.py`)

After the LLM call in `_build_mermaid()`, extract both the diagram DSL and the purpose paragraph:

- Parse `purpose` block: `re.search(r"```purpose\s*(.*?)\s*```", text, re.DOTALL)`
- If found, strip and store in a local variable `purpose`
- **Normalize `purpose` to a single line**: replace any `\n` characters with a space so the stored HTML comment is always single-line. This is required because the router extracts it with a non-DOTALL regex: `re.search(r'<!-- purpose: (.*?) -->', content)`
- If not found, use a fallback: `"This diagram shows the top-level architecture of the system."`
- Return a tuple `(mermaid_dsl, purpose)` from `_build_mermaid()`

Update callers of `_build_mermaid()` to unpack the tuple. Store the purpose alongside the diagram by prepending it to the stored content as a comment marker:

```
<!-- purpose: {purpose text — single line, no newlines} -->
{mermaid_dsl}
```

This way the purpose is stored in `ProjectDoc.content` and can be extracted by the frontend template.

### 3. Semantic color palette in module diagram prompt (`module_gen.py`)

Locate `_generate_and_store_module_diagram()` in `orch/rag/module_gen.py`. Apply the same enhancements:

- Add the same `classDef` block instructions to the LLM prompt
- Add the same class-assignment rules
- Add structural-elements-only instruction: "Show only: controllers, API handlers, services, repositories, data access layers, integration adapters, core domain models. Do NOT show: utility classes, helpers, DTOs, config objects."
- Change diagram direction to `LR` (left-to-right) instead of `TD` — module internals read better horizontally
- Add "Why" instruction: after the diagram, output a `purpose` block as above
- Extract purpose from response using the same regex; fallback: `"This diagram shows the internal component structure of the {module_name} module."`
- Normalize purpose to a single line (replace `\n` with space) before storing
- Prepend `<!-- purpose: {purpose — single line} -->` to the stored content

### 4. Keep existing elk frontmatter injection logic

Do not break the existing `elk_frontmatter` injection logic. The `<!-- purpose: -->` comment must be prepended before the elk frontmatter line so the final stored format is:

```
<!-- purpose: This diagram shows... -->
---
config:
  layout: elk
---
graph LR
  ...
  classDef api fill:#DBEAFE,...
  ...
```

---

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Key rules:
- Use `asyncio.to_thread()` for blocking LLM calls (already done — preserve pattern)
- `DocService` session patterns — follow existing `store_arch_diagram()` closure pattern
- No `importlib.reload()` in tests

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write tests first in `tests/unit/test_rag_mapgen.py` and `tests/unit/test_rag_module_gen.py`:
   - Mock the LLM response to include both a `mermaid` block and a `purpose` block
   - Assert `_build_mermaid()` returns a tuple `(dsl, purpose)`
   - Assert the stored content starts with `<!-- purpose:`
   - Assert the DSL contains `classDef api`

2. **GREEN**: Implement the changes to pass the tests.

3. **REFACTOR**: Ensure no duplication between `mapgen.py` and `module_gen.py` for the classDef block — extract to a `_MERMAID_CLASSDEF` module-level constant string used by both prompts.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting complete:
1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit`

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00067",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/rag/mapgen.py",
    "orch/rag/module_gen.py"
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
