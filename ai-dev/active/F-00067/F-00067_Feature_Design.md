# F-00067: Documentation Visual Design Overhaul

**Type**: Feature
**Priority**: High
**Created**: 2026-04-29
**Status**: Draft

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

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No database schema changes are required for this feature.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

Auto-generated code maps and component documentation are currently unreadable "walls" of black-and-white text and flat Mermaid diagrams with no color, no visual anchors, and no navigational structure. This feature overhauls the entire documentation visual stack: diagram generation prompts gain semantic color palettes and abstraction-level discipline; the dashboard's doc renderer gains GitHub-style callout blocks and richer typographic hierarchy; the `iw-doc-generator` skill templates gain "Why" sections and diagram guidance; and a new auto-generated index page per project provides a curated entry point into all documentation. Based on research R-00065.

## Project Context

Read `CLAUDE.md` for architecture, layer conventions, and hard rules (dashboard is FastAPI + Jinja2/htmx, RAG layer in `orch/rag/`, skills in `skills/`).

---

## Scope

### In Scope

- **Diagram prompt enhancement** (`orch/rag/mapgen.py`, `orch/rag/module_gen.py`): add semantic `classDef` color palette, "Why" paragraph generated alongside diagram DSL, abstraction-level instruction (structural elements only — no utilities/DTOs), direction choice (TD for arch, LR for modules)
- **Dashboard callout rendering** (`dashboard/templates/docs_detail.html`): parse GitHub-style `> [!NOTE]`, `> [!WARNING]`, `> [!DANGER]`, `> [!TIP]` blockquotes and render as colored admonition blocks
- **Dashboard typographic hierarchy** (`dashboard/templates/docs_detail.html`): differentiate H1/H2/H3 by weight AND color, not just size; increase body line-height; enforce max-width for readability
- **Diagram fragment context** (`dashboard/templates/fragments/code_architecture_diagram.html`, `code_module_diagram.html`): render the "Why" purpose paragraph above each diagram, expose diagram purpose in the UI
- **In-page Table of Contents** (`dashboard/templates/docs_detail.html`): auto-generate TOC from H2/H3 headings, render as sticky sidebar or anchor list for docs > 800 words
- **`iw-doc-generator` skill updates** (`skills/iw-doc-generator/references/module-doc-template.md`, new `skills/iw-doc-generator/references/diagram-guidelines.md`): add "Why" section, callout usage rules, diagram color spec, sync to all managed projects via `iw skills sync`
- **`iw-tech-doc-writer` diagram guidelines update** (`skills/iw-tech-doc-writer/references/diagram-guidelines.md`): add semantic color palette and "Why paragraph" rule
- **Index page generation** (`orch/rag/index_gen.py`): new module that generates a `code-index` ProjectDoc per project after `CodeIndexJob` completes; the index page lists all doc types with links and one-line descriptions

### Out of Scope

- PDF rendering improvements (separate `iw-doc-system` concern)
- Diagram type additions (e.g., sequence diagrams for code flow) — diagram type is chosen by the LLM; this feature only improves the styling prompt
- Chat UI visual improvements — handled in F-00068
- New database columns or schema changes
- Changing the Ollama model or RAG retrieval logic

---

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | Enhance diagram prompts in `mapgen.py` + `module_gen.py`: color palette, "Why" paragraph, abstraction guidance | S02, S03 |
| S02 | `frontend-impl` | Dashboard: callout rendering, typographic hierarchy, TOC, diagram fragment "Why" slot | S01, S03 |
| S03 | `template-impl` | Skill file updates: `iw-doc-generator` template + new diagram-guidelines; `iw-tech-doc-writer` diagram-guidelines; `iw skills sync` | S01, S02 |
| S04 | `code-review-impl` | Review S01 | — |
| S05 | `code-review-impl` | Review S02 | S04 |
| S06 | `code-review-impl` | Review S03 | S04, S05 |
| S07 | `backend-impl` | Index page generation: `orch/rag/index_gen.py`, hook into `CodeIndexJob` | after S04–S06 |
| S08 | `code-review-impl` | Review S07 | — |
| S09 | `tests-impl` | Unit tests for diagram prompt builders, index generator; integration test for full index doc creation; regression tests for callout CSS classes | — |
| S10 | `code-review-impl` | Review S09 | — |
| S11 | `code-review-final-impl` | Global cross-layer review | — |
| S12 | `qv-gate` | lint | — |
| S13 | `qv-gate` | format | — |
| S14 | `qv-gate` | typecheck | — |
| S15 | `qv-gate` | unit-tests | — |
| S16 | `qv-gate` | integration-tests | — |
| S17 | `qv-browser` | Browser verification | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None — existing `ProjectDoc` / `ProjectDocVersion` tables store the new index doc

### API Changes

- **New endpoints**: None (index page doc is fetched via existing `/project/{id}/docs/{doc_id}` route)
- **Modified endpoints**: None

### Frontend Changes

- **Modified templates**:
  - `dashboard/templates/docs_detail.html` — callout CSS + JS parser, TOC generator, enhanced prose-doc hierarchy
  - `dashboard/templates/fragments/code_architecture_diagram.html` — "Why" paragraph slot
  - `dashboard/templates/fragments/code_module_diagram.html` — "Why" paragraph slot
- **Modified Python rendering** (wherever `content_html` is computed in the docs router): add callout post-processing if done server-side

---

## Semantic Color Palette (canonical — all layers must use this)

Use these colors consistently across diagram prompts AND diagram CSS rendering:

| Class | Role | Fill | Stroke | Text |
|-------|------|------|--------|------|
| `api` | API / router / CLI entry points | `#DBEAFE` | `#3B82F6` | `#1E3A5F` |
| `data` | Database / repository / storage | `#D1FAE5` | `#10B981` | `#065F46` |
| `worker` | Background jobs / daemon / pipeline | `#FEF3C7` | `#F59E0B` | `#78350F` |
| `external` | External services / 3rd-party APIs | `#F3F4F6` | `#9CA3AF` | `#374151` |
| `ui` | Dashboard / frontend | `#EDE9FE` | `#8B5CF6` | `#3B0764` |
| `core` | Core orchestration / services | `#FEE2E2` | `#EF4444` | `#7F1D1D` |

---

## Callout Rendering Spec (canonical — frontend and skill templates must match)

GitHub-style blockquote callouts must be detected and rendered as styled div blocks.

Detection pattern (in rendered HTML or raw Markdown):
```
> [!NOTE]     → blue   — ℹ️  supplementary context
> [!TIP]      → green  — 💡  best practice / shortcut
> [!WARNING]  → amber  — ⚠️  behavior reader must not miss
> [!DANGER]   → red    — 🚨  breaking / destructive behavior
> [!IMPORTANT]→ purple — 📌  critical information
```

Each callout renders as:
```html
<div class="callout callout-{type}">
  <div class="callout-header">
    <span class="callout-icon">{emoji}</span>
    <span class="callout-label">{TYPE}</span>
  </div>
  <div class="callout-body">{content}</div>
</div>
```

CSS color tokens:
- `note`: border `#3B82F6`, bg `#EFF6FF`, label `#1D4ED8`
- `tip`: border `#10B981`, bg `#ECFDF5`, label `#065F46`
- `warning`: border `#F59E0B`, bg `#FFFBEB`, label `#92400E`
- `danger`: border `#EF4444`, bg `#FEF2F2`, label `#991B1B`
- `important`: border `#8B5CF6`, bg `#F5F3FF`, label `#4C1D95`

---

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00067/F-00067_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00067/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00067/prompts/F-00067_S01_Backend_prompt.md` | Prompt | Diagram prompt enhancement |
| `ai-dev/active/F-00067/prompts/F-00067_S02_Frontend_prompt.md` | Prompt | Dashboard template updates |
| `ai-dev/active/F-00067/prompts/F-00067_S03_Template_prompt.md` | Prompt | Skill file updates |
| `ai-dev/active/F-00067/prompts/F-00067_S04_CodeReview_Backend_prompt.md` | Prompt | Review S01 |
| `ai-dev/active/F-00067/prompts/F-00067_S05_CodeReview_Frontend_prompt.md` | Prompt | Review S02 |
| `ai-dev/active/F-00067/prompts/F-00067_S06_CodeReview_Template_prompt.md` | Prompt | Review S03 |
| `ai-dev/active/F-00067/prompts/F-00067_S07_Backend_IndexPage_prompt.md` | Prompt | Index page generation |
| `ai-dev/active/F-00067/prompts/F-00067_S08_CodeReview_IndexPage_prompt.md` | Prompt | Review S07 |
| `ai-dev/active/F-00067/prompts/F-00067_S09_Tests_prompt.md` | Prompt | Test coverage |
| `ai-dev/active/F-00067/prompts/F-00067_S10_CodeReview_Tests_prompt.md` | Prompt | Review S09 |
| `ai-dev/active/F-00067/prompts/F-00067_S11_CodeReview_Final_prompt.md` | Prompt | Global review |
| `ai-dev/active/F-00067/prompts/F-00067_S17_BrowserVerification_prompt.md` | Prompt | Browser verification |
| `orch/rag/mapgen.py` | Modified | Enhanced `_build_mermaid()` |
| `orch/rag/module_gen.py` | Modified | Enhanced `_generate_and_store_module_diagram()` |
| `orch/rag/index_gen.py` | New | Index page generator |
| `dashboard/templates/docs_detail.html` | Modified | Callouts, TOC, prose hierarchy |
| `dashboard/templates/fragments/code_architecture_diagram.html` | Modified | "Why" slot |
| `dashboard/templates/fragments/code_module_diagram.html` | Modified | "Why" slot |
| `skills/iw-doc-generator/references/module-doc-template.md` | Modified | "Why" section, callouts |
| `skills/iw-doc-generator/references/diagram-guidelines.md` | New | Color palette, abstraction rules |
| `skills/iw-tech-doc-writer/references/diagram-guidelines.md` | Modified | Color palette, "Why" rule |

---

## Acceptance Criteria

### AC1: Semantic colors appear in generated diagrams

```
Given a project has completed a code map generation
When the architecture diagram or module diagram is viewed in the dashboard
Then each node is colored according to its architectural role (API=blue, data=green, worker=amber, external=gray, ui=purple, core=red) using the canonical palette
And a legend or classDef block is present in the Mermaid DSL
```

### AC2: "Why" paragraph appears above each diagram

```
Given any architecture or module diagram is rendered in the dashboard
When the diagram section is viewed
Then a short paragraph (1–2 sentences) describing what the diagram shows and when to use it appears immediately above the Mermaid diagram
```

### AC3: Callout blocks render correctly in docs

```
Given a document with content containing "> [!WARNING] some text"
When the document is viewed in the docs detail page
Then the blockquote is rendered as a styled callout div with the correct border color (amber), icon (⚠️), and label (WARNING)
And plain blockquotes (without [!TYPE]) continue to render as before
```

### AC4: In-page TOC is generated for long documents

```
Given a document whose markdown content contains 3 or more H2/H3 headings
When the document is viewed on the docs detail page
Then a Table of Contents section is rendered (either sticky sidebar or top-anchored list) with links to each H2/H3 heading
```

### AC5: Index page is generated after code map run

```
Given a project whose CodeIndexJob has completed successfully
When "Generate Code Map" is run (or manually triggered)
Then a "code-index" ProjectDoc exists for the project
And it contains sections linking to: architecture overview, module docs, diagrams, API docs (if any)
And each entry includes a one-line description of the document's purpose
```

### AC6: Typographic hierarchy is visually distinct

```
Given any document is viewed in the docs detail page
When the page contains H1, H2, and H3 headings
Then H1 has font-weight 700 and a bottom border
And H2 has font-weight 600, a border-bottom, and is visually distinct from H1
And H3 has font-weight 600 and a muted color, visually distinct from H2
```

---

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Diagram with no components | LLM returns empty graph | Fallback `graph TD\n  A[System]` renders without crash |
| Document with no H2/H3 headings | Short doc, only H1 | TOC is not rendered (or renders empty gracefully) |
| Unknown callout type `> [!CUSTOM]` | Non-standard type in content | Falls back to plain blockquote render — no crash, no blank section |
| Missing "Why" metadata | Old diagram doc without purpose field | Fragment renders without purpose paragraph — no template error |
| Index page triggered on project with zero docs | No ProjectDocs exist | Index page generates with empty sections and a note: "No documentation yet" |
| Callout with multi-line body | `> [!NOTE]\n> Line 1\n> Line 2` | Both lines captured in callout body |

---

## Invariants

1. All Mermaid DSL stored in `ProjectDoc.content` (for `doc_type=diagram`) is valid Mermaid — never breaks the diagram renderer.
2. The `classDef` color palette in `mapgen.py` and `module_gen.py` is always identical to the canonical palette in this design doc.
3. Plain blockquotes (without `[!TYPE]`) are never styled as callouts — the parser must require the exact `[!TYPE]` prefix.
4. `code-index` doc is always of `doc_type=architecture` and `tier=fully_automated`.
5. `iw skills sync` is always called after any skill file modification in S03.
6. The prose-doc TOC only links to headings that have anchor IDs in the rendered HTML — broken anchors are never emitted.

---

## Dependencies

- **Depends on**: R-00065 (research completed ✓)
- **Blocks**: F-00068 (Chat UI visual improvements — shares callout CSS design; F-00067 defines the canonical palette and callout spec)

---

## TDD Approach

- **Unit tests** (`tests/unit/test_rag_mapgen.py`, `tests/unit/test_rag_module_gen.py`):
  - `_build_mermaid()` output contains `classDef` with all 6 color classes
  - `_build_mermaid()` output contains a purpose comment/note node
  - Module diagram prompt contains structural-elements-only instruction
- **Unit tests** (`tests/unit/test_rag_index_gen.py`):
  - `generate_index_page()` groups docs by type correctly
  - `generate_index_page()` produces valid Markdown with section headers
  - Empty project produces index with empty-section placeholders
- **Integration tests** (`tests/integration/test_rag_index_gen.py`):
  - Full round-trip: index doc is created in DB with correct `doc_id`, `doc_type`, `tier`
- **Frontend tests** (if applicable): callout CSS classes are present in compiled output
- **Edge cases**: unknown callout type falls back to plain blockquote; zero-heading doc skips TOC

---

## Notes

- The canonical semantic color palette defined in this design doc is the source of truth. Both S01 (backend) and S02 (frontend diagram fragment styling) must use the exact same hex values. The S03 skills agent must also embed these values in the diagram-guidelines reference file.
- The "Why" paragraph is generated by the LLM as part of the diagram generation prompt, then stored prepended to the diagram DSL content (separated by a `<!-- purpose -->` comment marker). The frontend fragment extracts and renders it separately from the Mermaid block.
- TOC generation should be done in JavaScript on the client side (after `content_html` is injected) to avoid server-side HTML parsing complexity.
- `iw skills sync` requires that the user has the managed projects available locally; the S03 agent should run it and report any sync errors as non-blocking notes (not blockers), since some projects may be on different machines.
- This feature does NOT change what the LLM generates in terms of diagram *content* — only the *styling instructions* in the prompt and the *rendering* in the UI. The LLM still decides which nodes to include.
