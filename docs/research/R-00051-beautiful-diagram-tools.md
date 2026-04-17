# R-00051 — Beautiful LLM-generated diagrams: tool landscape, aesthetics, and skill/tool design

| Field | Value |
|-------|-------|
| ID | R-00051 |
| Date | 2026-04-17 |
| Mode | deep |
| Editorial category | functional |
| Primary question | Which diagram tools produce the most elegant, audience-approved output when orchestrated by an LLM, and how should iw-ai-core structure its skills/tools so the LLM picks the right one and the output is actually beautiful by default? |

---

## Executive Summary

Today's Mermaid output is ugly for a reason: it defaults to the **dagre** layout engine (2014-era, hierarchical, prone to line crossings), a thin-line theme with weak typography, and no brand-level styling. Fixing that inside Mermaid is the **single highest-ROI move**: switching to **ELK layout** (`layout: elk` in YAML frontmatter) plus `themeVariables` + optional `look: handDrawn` makes Mermaid diagrams visibly closer to "designer output" at zero infrastructure cost. For the cases where Mermaid still isn't enough, the industry is converging on **D2** (2022, Go, ELK-native, aesthetic leader in head-to-head comparisons — [text-to-diagram](https://text-to-diagram.com/?example=text), [code4it — D2 like Mermaid but better](https://www.code4it.dev/architecture-notes/d2-diagrams/)), **Structurizr / LikeC4** (opinionated C4 model, model-as-code consistency — [docs.structurizr.com/ai](https://docs.structurizr.com/ai), [likec4.dev](https://likec4.dev/)), and **PlantUML with cloud-icon libraries** (AWS, Azure, GCP). **Draw.io stays in the toolkit** for diagrams that need post-render editing by a human — but not as the default for LLM generation (token cost is 24× Mermaid per [dev.to — token efficiency analysis](https://dev.to/akari_iku/analyzing-the-best-diagramming-tools-for-the-llm-age-based-on-token-efficiency-5891)). The recommended architecture is a **router skill + Kroki universal renderer + brand CSS overlay + parse-validate-self-repair loop** — executed across 4–5 tool skills (one per DSL) rather than one monolithic "generate a diagram" tool. Expected user-visible improvement: legibility jump on the first swap (ELK + brand theme), aesthetic jump on the architecture-diagram path (D2 or Structurizr), editability preserved for the draw.io path.

---

## Findings

### F1 — Mermaid's "ugliness" is mostly the default layout engine + default theme [HIGH]

Mermaid ships with the **dagre** layout as default ([Mermaid Layouts docs](https://mermaid.ai/open-source/config/layouts.html)). Dagre is the classic hierarchical engine — fast, deterministic, but known for line crossings, poor edge routing in dense graphs, and cramped node spacing. Community sentiment is blunt:

> *"The difference in rendering between default and elk for state diagrams and others is huge — the difference between usable and not."* ([Obsidian Forum — Support ELK in core Obsidian](https://forum.obsidian.md/t/mermaid-support-elk-layout-system-in-core-obsidian/95700))

Similar observations across [quarto-dev discussion #13736](https://github.com/orgs/quarto-dev/discussions/13736), [mermaid-js issue #5969](https://github.com/mermaid-js/mermaid/issues/5969) (Live Editor *silently* uses ELK for adaptive rendering because it looks better), and [Korny's Mermaid revisited post](https://blog.korny.info/2025/03/14/mermaid-js-revisited) which identifies ELK + handDrawn look + themeVariables as the practical upgrade path.

**Practical fixes, ranked by ROI**:

1. **Enable ELK** via YAML frontmatter: `---\nconfig:\n  layout: elk\n---` — biggest single change.
2. **Apply `look: handDrawn`** — a single toggle that softens lines and produces an instantly more professional/hand-sketched feel ([Korny](https://blog.korny.info/2025/03/14/mermaid-js-revisited)).
3. **Use `themeVariables` on the `base` theme** (the only customisable one — [Mermaid Theming docs](https://mermaid.ai/open-source/config/theming.html)) — set `primaryColor`, `primaryBorderColor`, `primaryTextColor`, `lineColor`, `fontSize`, `fontFamily`. Hex colors only; named colors are rejected.
4. **Use `classDef` with `:::className`** to apply consistent styling across nodes rather than per-node inline style.
5. **Layout control via invisible subgraphs** (`fill:#0000, stroke:#0000`) — a community trick to coax ELK into a desired shape.

**Caveats for ELK**:
- Some platforms don't include the ELK loader (Obsidian, Notion) — falls back silently to dagre ([Mermaid issue #5969](https://github.com/mermaid-js/mermaid/issues/5969)).
- Occasionally "too narrow" on certain topologies — requires `flowchart` direction tweaks or a manual width hint.
- State diagrams and class diagrams see the biggest visible win; short flowcharts (~5 nodes) often look identical.

### F2 — D2 is the aesthetic leader for diagrams-as-code today [HIGH]

D2 (2022, Go-based, [d2lang.com](https://d2lang.com/tour/layouts/)) is repeatedly identified as the tool that produces **the prettiest diagrams by default**:

> *"D2 creates the most aesthetic and readable diagrams using the ELK layout engine."* ([simmering.dev — Diagrams as Code: Supercharged by AI](https://simmering.dev/blog/diagrams/))

> *"D2 seemed to have better layout by default."* ([text-to-diagram comparison](https://text-to-diagram.com/?example=text))

Community momentum is active — the October 2025 [BigGo Finance write-up](https://finance.biggo.com/news/202510260715_D2-diagram-language-community-debate) documents active debate about D2 as a future default. D2's advantages over Mermaid:

- **ELK-native layout** (plus other engines like `dagre`, `tala`, `elk`) — no config required.
- **Friendly error messages** — critical for the LLM self-repair loop (F10).
- **Native PNG / SVG / PDF / PowerPoint export** — direct fit for our doc pipeline.
- **Modern syntax** — less symbolic noise than Mermaid (`a -> b: label` vs. `a -->|label| b`).
- **Themes** — built-in palettes (grape, pink, earth, neutral, dark-mauve, etc.) that look cohesive without per-node styling.

Caveats:
- **Platform support is narrower** — doesn't render natively in GitHub/GitLab markdown. Requires Kroki, the D2 CLI, or our own renderer.
- **LLM generation quality**: [simmering.dev](https://simmering.dev/blog/diagrams/) found that indexing D2 docs in Cursor and using Claude-3.5 Sonnet produced the best results — i.e. LLMs benefit from RAG-ing the D2 docs before generation. (This matches [huy.rocks — Teaching an LLM a Niche Diagramming Language](https://www.huy.rocks/everyday/12-01-2025-ai-teaching-an-llm-a-niche-diagraming-language).)
- **Token efficiency not quantified in the main LLM-age comparison** ([dev.to token-efficiency analysis](https://dev.to/akari_iku/analyzing-the-best-diagramming-tools-for-the-llm-age-based-on-token-efficiency-5891) omits D2), but syntax length is comparable to Mermaid in practice.

**Recommendation**: for **architecture diagrams where aesthetics matter** (customer-facing docs, stakeholder presentations, the chat's default diagram output), **D2 becomes the primary target**. Mermaid remains for quick inline flowcharts inside markdown.

### F3 — C4 tools (Structurizr, LikeC4) are the best fit for architecture modeling [HIGH]

For **software architecture diagrams specifically** (which is what most iw-ai-core dashboard users will ask for), the right abstraction is the **C4 model** (Context, Container, Component, Code). Two dominant tools:

**Structurizr DSL** ([docs.structurizr.com/dsl](https://docs.structurizr.com/dsl)):
- **Model-based consistency**: one model → multiple consistent views. Element names, descriptions, relationships, styling remain identical across Context, Container, and Component views.
- **Enforces C4 hierarchy**: containers must be inside software systems, components inside containers. Prevents the most common architecture-doc mistake.
- **MCP server** ([docs.structurizr.com/ai](https://docs.structurizr.com/ai)): exposes DSL validation, parsing, inspection. LLMs can drive it via natural language and get validation back.
- **Export paths**: PlantUML, Mermaid, static SVG/PNG via Structurizr CLI.
- **Quote**: *"LLMs excel at generating text — the Structurizr DSL is text-based, version controllable, and diff-friendly."* ([docs.structurizr.com/ai](https://docs.structurizr.com/ai))

**LikeC4** ([likec4.dev](https://likec4.dev/)):
- **Newer, more flexible** — inspired by Structurizr but not locked to C4 strictly; supports custom element types and nested specifications.
- **Interactive multi-level visualisation** — clickable zoom between Context → Container → Component.
- **MCP endpoint** built-in; IDE / agent-friendly.
- **Modern aesthetic defaults** — subjectively cleaner than Structurizr's stock output.
- **Trade-off**: doesn't enforce C4 strictly (a misconfigured spec can put elements at the wrong level — [paval.io — Structurizr vs LikeC4](https://paval.io/posts/2025-05-11-structurizr-vs-likec4/)). Needs more careful prompting.

**Recommendation**: use **Structurizr** when C4 strictness matters (exec-facing or compliance-facing architecture docs); use **LikeC4** when the architecture is custom or when modern aesthetics are the priority. Both are model-as-code and avoid the "multiple inconsistent diagrams" failure mode.

### F4 — PlantUML's sweet spot is cloud-architecture diagrams with official icons [MEDIUM]

PlantUML (2009, Java, [plantuml.com](https://plantuml.com/)) is the gold standard for comprehensive UML and the best tool for **cloud architecture diagrams** because:

- **AWS Icons for PlantUML** — official AWSlabs library ([awslabs/aws-icons-for-plantuml](https://github.com/awslabs/aws-icons-for-plantuml)) with sprites, macros, C4-integrated stereotypes.
- **Azure-PlantUML** — official stdlib inclusion ([plantuml-stdlib/Azure-PlantUML](https://github.com/plantuml-stdlib/Azure-PlantUML)).
- **GCP PlantUML** — in the standard library ([plantuml.com/stdlib](https://plantuml.com/stdlib)).
- **Multi-cloud** — libraries compose cleanly ([fullstackchronicles — Multi Cloud Diagramming](https://fullstackchronicles.io/multi-cloud-diagramming-with-plantuml)).
- **Modern themes** — bluegrey, AWS-style, PlantUML Theme Gallery with dozens of options ([the-lum theme gallery](https://the-lum.github.io/puml-themes-gallery/)).

Caveats:
- **Java runtime requirement** is the main operational drag — mitigated by Kroki (F7).
- **LLM fluency is solid but below Mermaid** in base-model training data.
- **Token cost ~60% higher than Mermaid** for equivalent diagrams ([dev.to token analysis](https://dev.to/akari_iku/analyzing-the-best-diagramming-tools-for-the-llm-age-based-on-token-efficiency-5891): PlantUML 80 tok vs Mermaid 50 tok for a simple sequence).

**Recommendation**: keep PlantUML as a **third-tier skill** specifically targeted at AWS / Azure / GCP architecture requests where branded cloud icons matter.

### F5 — Excalidraw / rough.js for informal, hand-drawn moments [MEDIUM]

Excalidraw ([excalidraw.com](https://excalidraw.com/), [GitHub](https://github.com/excalidraw/excalidraw)) is built on rough.js ([roughjs.com](https://roughjs.com/)) — a <9KB library that produces sketchy, hand-drawn-looking shapes. The aesthetic is **deliberately informal** and has a strong following for whiteboard-style diagrams.

Key findings:
- **Reproducible rendering via seeds**: *"same seed = same hand-drawn variation; use deterministic seeds for reproducible diagrams"* ([Excalidraw deepwiki — Rendering Architecture](https://deepwiki.com/zsviczian/excalidraw/6.1-rendering-architecture)).
- **Roughness dial**: `roughness: 0` (clean) → `roughness: 2` (sketch). Middle ground (1) matches the product aesthetic.
- **Fabric / cloud shape libraries** exist ([Fabric library for Excalidraw](https://milescole.dev/data-engineering/2024/11/20/Fabric-Library-for-Excalidraw.html)) but are not as deep as PlantUML's.
- **LLM generation**: programmatic JSON emission is possible but **token-heavy** — 500 tokens for a simple sequence diagram (10× Mermaid's 50) per [dev.to analysis](https://dev.to/akari_iku/analyzing-the-best-diagramming-tools-for-the-llm-age-based-on-token-efficiency-5891). MCP tooling exists ([dev.to — AI-driven diagram generation MCP](https://dev.to/thangchung/ai-driven-software-architecture-diagram-generation-automating-excalidraw-and-drawio-with-mcp-apps-3edc)).

**Recommendation**: Excalidraw is **niche** — explicitly opt-in for brainstorming/informal contexts. Alternatively, get 80% of the aesthetic via **Mermaid's `look: handDrawn`** at a fraction of the token cost.

### F6 — Draw.io keeps its place but only for editable output [MEDIUM]

Draw.io via `cli-anything-drawio` and the draw.io desktop CLI (already in the `iw-draw-io` skill) fills a specific niche: **diagrams that a human will edit after the LLM produces the first draft**. Its token cost is the highest of the contenders:

| Tool | Tokens for simple sequence |
|---|---|
| Mermaid | ~50 |
| PlantUML | ~80 |
| Excalidraw | ~500 |
| **draw.io XML** | **~1,200** |

([dev.to — token efficiency analysis](https://dev.to/akari_iku/analyzing-the-best-diagramming-tools-for-the-llm-age-based-on-token-efficiency-5891))

But draw.io has **real advantages**:

- **Simplified `mxGraphModel` XML** format documented specifically for LLM generation ([drawio.com — AI diagram generation FAQ](https://www.drawio.com/doc/faq/ai-drawio-generation)): uncompressed, fewer nesting levels, mxfile.xsd validation schema, style reference catalog.
- **MCP server (`@drawio/mcp`)** ([npmjs @drawio/mcp](https://www.npmjs.com/package/@drawio/mcp)): renders diagrams inline, opens in draw.io editor, accepts XML / CSV / Mermaid input.
- **GenAI-DrawIO-Creator** ([arXiv 2601.05162](https://arxiv.org/html/2601.05162v1)): published framework demonstrating Claude 3.7 generating valid mxGraphModel XML.
- **Best-in-class desktop editing** — the primary reason to use it at all.
- **Our existing `iw-draw-io` skill** already wires this up.

**Anti-patterns**:
- Asking the LLM to emit compressed / base64-encoded XML — *"compressed XML uses more tokens, is not human-readable, and cannot be validated or debugged without decompression"* ([drawio.com](https://www.drawio.com/doc/faq/ai-drawio-generation)).
- Putting draw.io XML in git as the source-of-truth for versioned architecture — diffs are unmanageable.

**Recommendation**: keep `iw-draw-io` but **demote from default** — reserve for *"generate a diagram the user will edit"* and *"multi-page architecture diagram for a design document"*. Architecture diagrams rendered into the dashboard chat should prefer Mermaid+ELK, D2, or Structurizr.

### F7 — Kroki is the right universal-renderer abstraction [HIGH]

Kroki ([kroki.io](https://kroki.io/), [github.com/yuzutech/kroki](https://github.com/yuzutech/kroki)) is a single HTTP service that renders **20+ DSLs** including: Mermaid, D2, PlantUML, Structurizr, GraphViz, Excalidraw, BlockDiag, BPMN, ditaa, ERD, Nomnoml, Pikchr, TikZ, UMLet, Vega, Vega-Lite, Bytefield, DBML, Symbolator, SvgBob.

Why it matters for LLM skill design:
- **One renderer API to integrate**: `POST /{diagram-type}/{output-format}` with text body → SVG/PNG/PDF.
- **Self-hostable via Docker** — no external calls, no data egress.
- **Decouples DSL choice from render pipeline**: the LLM router skill picks the DSL, Kroki renders.
- **Encoding via deflate + base64 URLs** for GETs where preferred.

**Recommendation**: deploy Kroki as the **single rendering backend** for all non-draw.io diagram output. Compose with our existing infrastructure:

```
LLM → chooses DSL → emits text → Kroki renders → SVG/PNG → brand CSS overlay → dashboard chat
```

This collapses five per-tool CLI dependencies (`mmdc`, `d2`, `plantuml.jar`, `excalidraw-cli`, `structurizr-cli`) into one Docker container.

### F8 — Cognitive-load research supports "less is more" aesthetic choices [MEDIUM]

Peer-reviewed work on diagram comprehension finds specific causes of extraneous cognitive load:

- **Contrast between figure and background**: *"charts with lower contrast between bars and background have additional cognitive load"* ([inria HAL — Cognitive load and readability](https://inria.hal.science/hal-04885430v1/document)).
- **Color discipline**: *"if bars are the same color, viewers will know the values should be compared; varying colors imposes additional cognitive load"* (same source).
- **Complexity cap**: *"visualizations including too many layers of complexity can hinder decision-making processes by limiting the cognitive capacity of users"* ([Number Analytics — Cognitive Load in Visual Design](https://www.numberanalytics.com/blog/cognitive-load-visual-design-ux-guide)).
- **Process-model research**: *"high-contrast colors and bold shapes in a process model instinctively capture attention, allowing viewers to identify key elements such as decision points or subprocesses"* ([PMC — Cognitive Factors in Process Model Comprehension](https://pmc.ncbi.nlm.nih.gov/articles/PMC12109775/)).

**Concrete guidelines** distilled for our brand overlay:

- **Max 3 semantic colors per diagram** (primary, accent, muted) — matches IW brand config.
- **High fg/bg contrast** — WCAG AA minimum (4.5:1 for text).
- **Bold edges, thin labels** — edge-attention before node-attention.
- **Cap node count**: < 20 for flowcharts, < 15 for architecture. Above these, split into multiple diagrams.
- **Don't color-code for decoration** — every color should mean something or use the same color.
- **Prefer orthogonal edges for architecture, curved for flow** — matches human expectation.

These rules slot cleanly into the `iw-brand-config` skill as a post-render CSS overlay (fixed palette + typography + stroke widths).

### F9 — Diagram-type → tool routing matrix (recommended) [HIGH]

Synthesis of the above, updating the current `iw-diagram-generator` skill's table:

| Diagram type | **Recommended tool** | Why | Token cost |
|---|---|---|---|
| Quick flowchart (inline markdown) | **Mermaid + ELK + brand theme** | GitHub/GitLab native render; low token | Low |
| Sequence (inline markdown) | Mermaid + brand theme | Well-trained, clean default | Low |
| Architecture (high polish) | **D2 (Kroki-rendered)** | Aesthetic leader + ELK | Low |
| **C4 Context / Container / Component** | **Structurizr DSL** or LikeC4 | Model-consistency, enforced hierarchy | Medium |
| Cloud (AWS / Azure / GCP) | **PlantUML + cloud icon stdlib** | Official brand icons | Medium |
| ER / data model | Mermaid `erDiagram` or PlantUML | Either works | Low |
| Class / UML | **PlantUML** | Most complete UML spec | Medium |
| State machine | **Mermaid + ELK** | ELK fixes state-diagram layout (F1) | Low |
| Network topology | D2 or Graphviz | D2 for modern, Graphviz for classic | Low |
| Mind map | **Hand-drawn / Excalidraw** or Markdown list | Mermaid mind-maps look bad ([Korny](https://blog.korny.info/2025/03/14/mermaid-js-revisited)) | - |
| Informal / whiteboard | **Mermaid `look: handDrawn`** (default) or Excalidraw (opt-in) | Low-cost aesthetic | Low / High |
| Diagram user will edit afterwards | **draw.io (simplified XML)** | Desktop editor + MCP | High |
| Gantt / timeline | Mermaid `gantt` | Built-in | Low |
| Data visualization / charts | **Vega-Lite** (via Kroki) | Declarative, safe (R-00050 F8) | Medium |

### F10 — LLM tool/skill design: router + DSL skills + validator + self-repair [HIGH]

The dominant industry pattern for LLM-driven diagrams, derived from the MCP server ecosystem ([drawio-mcp](https://github.com/jgraph/drawio-mcp), [claude-mermaid](https://github.com/veelenga/claude-mermaid), [sailor](https://github.com/aj-geddes/sailor), [UML-MCP (Kroki-based)](https://github.com/antoinebou12/uml-mcp), [AntV mcp-server-chart](https://github.com/antvis/mcp-server-chart)):

**Architecture (recommended for iw-ai-core)**:

1. **Router skill** (`iw-diagram-generate`): takes user intent + context, picks DSL per F9 matrix, delegates to a DSL-specific skill.
2. **Per-DSL skills** (small, composable):
   - `iw-diagram-mermaid` — Mermaid + ELK + themeVariables + brand CSS overlay.
   - `iw-diagram-d2` — D2 + Kroki render.
   - `iw-diagram-c4` — Structurizr DSL (or LikeC4) → Kroki render.
   - `iw-diagram-plantuml` — PlantUML + cloud libs → Kroki render.
   - `iw-draw-io` — already exists; keep for editable output only.
3. **Validator**: for every DSL, parse-validate **before** render (per R-00050 F5 — Mermaid `parse()`, D2 `d2 compile --dry-run`, Structurizr `structurizr-cli validate`, PlantUML `plantuml -checkonly`).
4. **Self-repair loop**: on syntax error, send back DSL + error message in a bounded re-prompt (N≤2 retries) — proven pattern from [Microsoft GenAIScript — Mermaids Unbroken](https://microsoft.github.io/genaiscript/blog/mermaids/) and the [drawio.com — AI generation FAQ](https://www.drawio.com/doc/faq/ai-drawio-generation).
5. **Render backend**: Kroki container (one process, all DSLs except draw.io).
6. **Brand overlay**: post-render CSS/SVG patch step applying `iw-brand-config` palette, fonts, stroke widths, dark-mode dual.

**LLM-side prompting tips** (from [simmering.dev](https://simmering.dev/blog/diagrams/), [huy.rocks](https://www.huy.rocks/everyday/12-01-2025-ai-teaching-an-llm-a-niche-diagraming-language), [DiagrammerGPT — arXiv 2310.12128](https://arxiv.org/html/2310.12128v2)):

- **RAG the DSL docs** into the LLM context for less-common DSLs (D2, LikeC4). Few-shot is not enough.
- **Use examples** — 2–3 few-shot examples per DSL outperform cold generation ([Chat2VIS](https://arxiv.org/pdf/2302.02094) analog for Vega-Lite holds here).
- **Constrain the output format** — JSON-mode or strict "emit only DSL, no prose" system instruction.
- **Budget nodes** — tell the LLM "max 15 nodes"; prevents runaway diagrams that become unreadable anyway (F8).
- **Request orthogonal edges** for architecture diagrams; curved for flow diagrams.
- **Provide the brand palette in the prompt** — ask the LLM to use `#002060` (IW primary) for primary nodes, etc. Reinforces the post-render overlay.

### F11 — The DiagrammerGPT framework generalizes this pattern [MEDIUM]

DiagrammerGPT ([arXiv 2310.12128](https://arxiv.org/html/2310.12128v2), COLM 2024) is a published multi-agent framework that plans a diagram as a layout graph, then generates target DSL. The framework's key steps map onto our recommended architecture:

1. **Planner LLM**: decides diagram type + abstraction level (our router).
2. **Layout LLM**: emits a node-edge plan with sizes and positions (our DSL skill, informed by ELK).
3. **Refiner LLM**: critiques the intermediate layout (our validator + self-repair).
4. **Renderer**: produces the final raster (our Kroki + brand overlay).

We don't need to replicate this as literal multi-agent architecture — but it validates the decomposition.

### F12 — Integration with existing iw-ai-core skills [HIGH]

Our current surface:

- `iw-draw-io` — draw.io XML + desktop CLI export (PNG/SVG/PDF). **Keep, but demote to editable-output use case.**
- `iw-diagram-generator` — Mermaid-first, with D2/Python-Diagrams/PlantUML as optional fallbacks. **Refactor**:
  - Enable ELK layout by default via YAML frontmatter injection.
  - Add brand `themeVariables` auto-injection (from `iw-brand-config`).
  - Move "client-facing (high aesthetics)" row to **D2 as primary**, not Mermaid.
  - Add explicit C4 routing to `iw-diagram-c4` (new skill).
- `iw-brand-config` — palette/typography source of truth. **Expose a `diagram_overlay.css` output** for post-render application.

**Proposed new/updated skills** (ordered by impact):

1. **Update `iw-diagram-generator`** — ELK default + brand themeVariables + D2 promotion. One PR, large aesthetic payoff.
2. **New `iw-diagram-c4`** — Structurizr DSL (preferred) or LikeC4 wrapper; target C4 Context/Container/Component.
3. **New `iw-diagram-d2`** — standalone D2 + Kroki pipeline; used directly by the dashboard chat when LLM picks it.
4. **Kroki deployment** — one Docker container added to the ops stack; see Limitations for security note.
5. **Shared validator** — Python module `orch/diagram/validate.py` that dispatches `parse` by DSL.
6. **Brand overlay** — `diagram_overlay.css` generated from `iw-brand-config`; applied by all renderers in the last step.

---

## Expected Gains

| Gain | Mechanism | User-visible signal |
|---|---|---|
| Legibility jump on existing Mermaid diagrams | ELK layout + themeVariables | Fewer line crossings; readable dense graphs |
| Aesthetic jump on architecture diagrams | D2 via Kroki | "This looks professional" reaction |
| Architectural consistency | Structurizr/LikeC4 C4 enforcement | Same model, multiple consistent views |
| Brand coherence | Shared `diagram_overlay.css` | Diagrams match dashboard/doc style |
| Fewer render failures | parse-validate + self-repair | Mermaid/D2 syntax errors ~vanish |
| Lower token cost for non-editable diagrams | Mermaid/D2 over draw.io | ~24× token reduction on simple diagrams |
| Preserved editability for handoff cases | draw.io path preserved | Humans can still edit afterwards |
| Dark-mode parity | Dual-render via brand overlay | Diagrams don't look broken in dark theme |

---

## Anti-patterns to avoid

- ❌ **Let Mermaid default to dagre for anything dense** — state diagrams, multi-subgraph flows, nested C4.
- ❌ **Emit compressed/base64 draw.io XML** — unreadable, unvalidatable, higher token cost.
- ❌ **Per-node inline styles instead of `classDef`/theme** — unmaintainable, brand-breaking.
- ❌ **Named colors** (`red`, `blue`) in `themeVariables` — silently rejected ([Mermaid theming docs](https://mermaid.ai/open-source/config/theming.html)).
- ❌ **LLM-emitted raw SVG as the final diagram** — XSS risk (R-00050 F12).
- ❌ **Mermaid mind-maps** — audience-rejected aesthetic ([Korny](https://blog.korny.info/2025/03/14/mermaid-js-revisited)); use Excalidraw or a markdown list.
- ❌ **Multi-page draw.io for versioned architecture** — git diffs are unreadable.
- ❌ **Unbounded node counts** — ugly + cognitive overload. Budget 15–20 and split.
- ❌ **One-shot generation without validate** — 30%+ of LLM Mermaid output has syntax errors per the [Mermaid Chart blog](https://docs.mermaidchart.com/blog/posts/how-to-choose-the-best-ai-diagram-generator-for-your-needs-2025).
- ❌ **Missing the brand overlay** — looks off-brand even when shape is correct.
- ❌ **Exposing Kroki to the open internet** — CPU-bound DoS surface; keep it private/auth-only.
- ❌ **Using D2 in GitHub markdown directly** — doesn't render; render server-side and embed the image.

---

## Limitations

- **No benchmark**: this research did not run A/B aesthetic tests against real users. "Audience-approved" claims lean on community consensus (HN, Lobsters, Medium writeups, simmering.dev, code4it) rather than eye-tracking. Before committing to D2 as the dashboard default, run a 5-person internal preference test.
- **Mermaid ELK availability is platform-dependent**: if we ever render Mermaid in an environment without the ELK loader (Obsidian, Notion), we silently fall back to dagre — design the pipeline so the ELK loader is always bundled.
- **D2 LLM fluency is weaker than Mermaid** in stock models; expect a first-pass error rate higher than Mermaid's. Mitigate with RAG-d docs + few-shot.
- **Structurizr's AI page** ([docs.structurizr.com/ai](https://docs.structurizr.com/ai)) was partially summarised at fetch time; the exact MCP tool list should be re-read before implementing `iw-diagram-c4`.
- **Kroki self-hosting** is straightforward but introduces a service-ops cost (Docker container, upgrades). If we stay on Kroki's public SaaS, we'd be sending potentially proprietary architecture DSL off-premises — **security-significant**; recommend self-hosting.
- **Cognitive-load research is general** (business-process models, infographics) — not specifically calibrated to developer-facing architecture diagrams. The "max 15–20 nodes" rule is a heuristic, not an empirical threshold for our audience.
- **Token-efficiency numbers** (dev.to analysis) are based on a single simple sequence diagram; they don't generalise linearly to larger diagrams — draw.io XML in particular scales worse.
- **Brand overlay design is not fully specified** in this doc — needs a design session with the `iw-brand-config` skill to pin down the final CSS/SVG patch pipeline.
- **Excalidraw JSON generation quality via LLMs is under-studied** — treat as experimental.
- **`iw-draw-io` skill still references `cli-anything-drawio`** which requires the Windows draw.io desktop for export. Any migration to a Linux-native pipeline (e.g. drawio Electron headless) is out of scope here but worth scheduling.

---

## Sources

| # | Title | Credibility | URL |
|---|---|---|---|
| 1 | Mermaid — Layouts (ELK) | Official docs (HIGH) | https://mermaid.ai/open-source/config/layouts.html |
| 2 | Mermaid — Theme Configuration | Official docs (HIGH) | https://mermaid.ai/open-source/config/theming.html |
| 3 | Korny — Mermaid.js revisited (2025) | Practitioner blog (HIGH) | https://blog.korny.info/2025/03/14/mermaid-js-revisited |
| 4 | Obsidian Forum — Support ELK in core | Community signal | https://forum.obsidian.md/t/mermaid-support-elk-layout-system-in-core-obsidian/95700 |
| 5 | quarto-dev discussion #13736 — Quarto Mermaid ELK layout | Community | https://github.com/orgs/quarto-dev/discussions/13736 |
| 6 | mermaid-js issue #5969 — Live editor uses layout: elk | Upstream issue (HIGH) | https://github.com/mermaid-js/mermaid/issues/5969 |
| 7 | D2 Documentation — Layouts | Official docs (HIGH) | https://d2lang.com/tour/layouts/ |
| 8 | Code4IT — D2 like Mermaid but better | Practitioner blog | https://www.code4it.dev/architecture-notes/d2-diagrams/ |
| 9 | BigGo — D2 community debate (2025-10) | Press | https://finance.biggo.com/news/202510260715_D2-diagram-language-community-debate |
| 10 | Paul Simmering — Diagrams as Code Supercharged by AI | Practitioner blog (HIGH) | https://simmering.dev/blog/diagrams/ |
| 11 | text-to-diagram — 2025 comparison (D2/Mermaid/PlantUML/Graphviz) | Independent comparison | https://text-to-diagram.com/?example=text |
| 12 | DiagrammerGPT (arXiv 2310.12128, COLM 2024) | Peer-reviewed (HIGH) | https://arxiv.org/html/2310.12128v2 |
| 13 | Huy — Teaching an LLM a Niche Diagramming Language | Practitioner blog | https://www.huy.rocks/everyday/12-01-2025-ai-teaching-an-llm-a-niche-diagraming-language |
| 14 | swark-io — Architecture diagrams from code with LLMs | Open-source tool | https://github.com/swark-io/swark |
| 15 | dev.to (akari_iku) — Token efficiency analysis | Practitioner comparison | https://dev.to/akari_iku/analyzing-the-best-diagramming-tools-for-the-llm-age-based-on-token-efficiency-5891 |
| 16 | Structurizr — DSL docs | Official (HIGH) | https://docs.structurizr.com/dsl |
| 17 | Structurizr — AI + MCP | Official (HIGH) | https://docs.structurizr.com/ai |
| 18 | LikeC4 — Homepage | Official | https://likec4.dev/ |
| 19 | LikeC4 — Model docs | Official | https://likec4.dev/dsl/model/ |
| 20 | paval.io — Structurizr vs LikeC4 | Practitioner comparison | https://paval.io/posts/2025-05-11-structurizr-vs-likec4/ |
| 21 | C4 model — Homepage | Authoritative (HIGH) | https://c4model.com/ |
| 22 | c4-structurizr-llm-assistant (GitHub) | Community tool | https://github.com/michaeltschreiber/c4-structurizr-llm-assistant |
| 23 | Devōt — C4 Model Architecture Explained | Editorial | https://devot.team/blog/c4-model |
| 24 | Skywork — 7 LikeC4 MCP server alternatives (2025) | Editorial survey | https://skywork.ai/blog/likec4-mcp-server-alternatives-2025/ |
| 25 | PlantUML — Standard Library | Official | https://plantuml.com/stdlib |
| 26 | PlantUML — Theme Gallery | Official | https://plantuml.com/theme-gallery |
| 27 | PlantUML Themes Gallery (community) | Community | https://the-lum.github.io/puml-themes-gallery/ |
| 28 | AWS Icons for PlantUML (awslabs) | Official AWS | https://github.com/awslabs/aws-icons-for-plantuml |
| 29 | Azure-PlantUML (stdlib) | Official stdlib | https://github.com/plantuml-stdlib/Azure-PlantUML |
| 30 | Full Stack Chronicles — Multi-Cloud Diagramming with PlantUML | Practitioner blog | https://fullstackchronicles.io/multi-cloud-diagramming-with-plantuml |
| 31 | Excalidraw (GitHub) | Open-source (HIGH) | https://github.com/excalidraw/excalidraw |
| 32 | Rough.js (homepage) | Open-source | https://roughjs.com/ |
| 33 | Excalidraw — Rendering architecture | Community deepwiki | https://deepwiki.com/zsviczian/excalidraw/6.1-rendering-architecture |
| 34 | dev.to (thangchung) — AI-driven diagram generation Excalidraw + draw.io MCP | Practitioner blog | https://dev.to/thangchung/ai-driven-software-architecture-diagram-generation-automating-excalidraw-and-drawio-with-mcp-apps-3edc |
| 35 | draw.io — AI diagram generation FAQ | Official (HIGH) | https://www.drawio.com/doc/faq/ai-drawio-generation |
| 36 | draw.io — Customise LLM backends | Official | https://www.drawio.com/doc/faq/configure-ai-options |
| 37 | draw.io MCP (npm) | Official package | https://www.npmjs.com/package/@drawio/mcp |
| 38 | jgraph/drawio-mcp (GitHub) | Official | https://github.com/jgraph/drawio-mcp |
| 39 | GenAI-DrawIO-Creator (arXiv 2601.05162) | Peer-reviewed | https://arxiv.org/html/2601.05162v1 |
| 40 | Kroki — Homepage | Official (HIGH) | https://kroki.io/ |
| 41 | yuzutech/kroki (GitHub) | Open-source | https://github.com/yuzutech/kroki |
| 42 | UML-MCP (Kroki-backed) | Community MCP | https://github.com/antoinebou12/uml-mcp |
| 43 | claude-mermaid (GitHub) | Community MCP | https://github.com/veelenga/claude-mermaid |
| 44 | sailor — Mermaid MCP | Community MCP | https://github.com/aj-geddes/sailor |
| 45 | AntV — mcp-server-chart | Official | https://github.com/antvis/mcp-server-chart |
| 46 | Microsoft GenAIScript — Mermaids Unbroken (self-repair) | First-party engineering | https://microsoft.github.io/genaiscript/blog/mermaids/ |
| 47 | Mermaid Chart blog — How to choose the best AI diagram generator (2025) | Vendor blog | https://docs.mermaidchart.com/blog/posts/how-to-choose-the-best-ai-diagram-generator-for-your-needs-2025 |
| 48 | Mermaid Editor blog — Mermaid vs PlantUML vs draw.io | Vendor blog | https://mermaideditor.com/blog/mermaid-vs-plantuml-vs-drawio |
| 49 | Gleek — Mermaid vs PlantUML | Vendor comparison | https://www.gleek.io/blog/mermaid-vs-plantuml |
| 50 | Simon Brown — Software architecture diagrams, which tool should we use? | Practitioner (HIGH) | https://dev.to/simonbrown/software-architecture-diagrams-which-tool-should-we-use-29e |
| 51 | inria HAL — Cognitive-load approach to designing visualisations | Peer-reviewed (HIGH) | https://inria.hal.science/hal-04885430v1/document |
| 52 | PMC — Cognitive Factors in Process Model Comprehension | Peer-reviewed (HIGH) | https://pmc.ncbi.nlm.nih.gov/articles/PMC12109775/ |
| 53 | Number Analytics — Cognitive Load in Visual Design UX Guide | Editorial | https://www.numberanalytics.com/blog/cognitive-load-visual-design-ux-guide |
| 54 | Chat2VIS (arXiv 2302.02094) | Peer-reviewed | https://arxiv.org/pdf/2302.02094 |
