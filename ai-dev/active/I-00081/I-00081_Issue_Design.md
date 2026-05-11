# I-00081: Code page "Architecture Diagram" widget shows "Syntax error in text — mermaid version 11.14.0"

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-11
**Reported By**: User (sergio) — reproduced live on `iw-dev-01:9900`
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.) This item touches no Docker state — no container/volume/network commands, read-only `docker ps|inspect|logs` only if needed.

## ⛔ Migrations: agents generate, daemon applies

This item adds **no migrations** and touches no database schema. It only changes a dashboard router helper and two Jinja2 fragments, plus a new test file.

## Description

Opening a project's **Code** page (`/project/{id}/code`) shows a broken "Architecture Diagram" widget: instead of a rendered diagram it displays a wall of red error text ("Mermaid error: No diagram type detected matching given configuration for text: # IW AI Core Platform — Architecture Diagram > **Why this diagram?** … ```mermaid …") plus one or more "Syntax error in text / mermaid version 11.14.0" boxes. The rest of the Code page works. Reproduced live for `iw-ai-core` on `iw-dev-01:9900`.

## Project Context

Read the project's `CLAUDE.md` (and `dashboard/CLAUDE.md`, `orch/CLAUDE.md`, `orch/rag/CLAUDE.md`, `tests/CLAUDE.md`) for architecture, conventions, and hard rules — in particular: routers are thin (logic lives in `orch/`, though `code_ui.py` already houses small render helpers like `_preprocess_mermaid` / `_render_architecture_html`); never run `docker compose` against the orch DB; never run alembic against the live DB; `make lint` runs `scripts/check_templates.py` over Jinja2 templates; plain CSS goes directly into `dashboard/static/styles.css` when Tailwind can't recompile (not relevant here).

## Steps to Reproduce

1. Open `http://<dashboard-host>:9900/project/iw-ai-core/code` (any project whose `diagram-architecture` ProjectDoc was written by the `iw-doc-generator` doc-generation job, i.e. is a Markdown document with fenced ` ```mermaid ` blocks rather than a bare DSL).
2. Scroll to the "Architecture Diagram" section near the bottom of the left/main column.

**Expected**: The architecture diagram(s) from the `diagram-architecture` doc render as proper Mermaid SVG(s).

**Actual**: A red "Mermaid error: No diagram type detected matching given configuration for text: # IW AI Core Platform — Architecture Diagram …" block (the doc's whole Markdown source), plus three "Syntax error in text / mermaid version 11.14.0" boxes (one per failed `mermaid.render()` invocation).

## Browser Evidence

- `ai-dev/active/I-00081/evidences/pre/I-00081-bug-evidence.png` — the Code page scrolled to the "Architecture Diagram" widget, showing the raw Markdown rendered as red error text and three "Syntax error in text / mermaid version 11.14.0" boxes.
- `ai-dev/active/I-00081/evidences/pre/I-00081-snapshot.yml` — accessibility snapshot of the same page; the `.mermaid` div's text node is the full Markdown document (`# IW AI Core Platform — Architecture Diagram` … literal ` ```mermaid ` fences …), and three error SVGs appear in `document.body`.

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "http://<dashboard-host>:9900/project/iw-ai-core/code"
playwright-cli eval "document.getElementById('code-arch-diagram')?.scrollIntoView({block:'center'})"
playwright-cli snapshot   # the .mermaid div text == the whole Markdown doc; "Syntax error in text" SVGs present
playwright-cli screenshot # → .playwright-cli/page-<ts>.png
```

## Root Cause Analysis

`dashboard/routers/code_ui.py` treats the `diagram-architecture` ProjectDoc as a **bare Mermaid DSL string**:

- `code_page()` (`code_ui.py:147-156`) and `code_architecture()` (`code_ui.py:260-300`) call `arch_diagram_doc = DocService(db).get_doc(project_id, "diagram-architecture")`, extract `arch_purpose` from a `<!-- purpose: … -->` comment via regex, then `arch_diagram_dsl = _clean_diagram_dsl(arch_diagram_doc.content)`.
- `_clean_diagram_dsl()` (`code_ui.py:35-47`) only (a) strips HTML comments `<!--.*?-->` and (b) strips a **single leading** `---\n…\n---` YAML front-matter block. It does **not** unwrap ` ```mermaid ` fences, strip Markdown prose (`# H1`, `> blockquotes`), or handle a multi-diagram document.
- `arch_diagram_dsl` is passed to `fragments/code_architecture_diagram.html:9`, which injects it verbatim into `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>`. `components/libs/mermaid.html`'s `iwRenderMermaid()` reads `node.textContent` and calls `mermaid.render(id, src)`.

That contract is correct for the `orch/rag/mapgen.py` code-understanding pipeline, which writes `content = f"<!-- purpose: {purpose} -->\n{dsl}"` (`mapgen.py:194`) — a bare DSL (optionally prefixed by a `---\nconfig:\n  layout: elk\n---` block, which `_clean_diagram_dsl` strips, because the dashboard's client-side Mermaid in `components/libs/mermaid.html` only calls `mermaid.initialize(...)` and never registers the ELK layout loader).

But the `diagram-architecture` ProjectDoc is **also** written by the `iw-doc-generator` skill via a `DocGenerationJob` (for `iw-ai-core`: `doc_generation_jobs` row `ea09df60-8454-46a5-9684-6e0e54e3d458`, public id `DOC-00057`, `skill_used='iw-doc-generator'`, completed 2026-05-11; the resulting `project_docs` row `iw-ai-core:diagram-architecture` has `generated_by='skill:iw-doc-generator'`, `doc_type=diagram`, `version=11`). That writer produces a **full Markdown document**: a `# IW AI Core Platform — Architecture Diagram` H1, `<!-- generated: … -->` / `<!-- doc_job: … -->` comments, three `> **Why this diagram?** …` blockquotes, and three ` ```mermaid ` fenced blocks (each with its own `---\nconfig:\n  layout: elk\n---` front-matter).

When `_clean_diagram_dsl()` runs on that, it removes the HTML comments and `.strip()`s — but the content starts with `# IW AI Core Platform …`, not `---`, so the front-matter strip is a no-op. The string handed to `mermaid.render()` is the whole Markdown blob (heading, blockquotes, literal ` ```mermaid ` fences). Mermaid 11.14.0 cannot parse it → it throws `No diagram type detected matching given configuration for text: …` (caught and dumped as red text by `iwRenderMermaid`'s catch block) **and** renders its own "Syntax error in text / mermaid version 11.14.0" error SVG into the DOM (once per `mermaid.render()` call — there are three: the page-template path, the `DOMContentLoaded` handler, and an htmx re-trigger — hence three boxes).

In short: two writers, one slug (`diagram-architecture`), incompatible content formats — and `code_ui.py` only understands one of them. The Code-page "Architecture Diagram" widget (added in F-00067 — `_clean_diagram_dsl`, the `<!-- purpose: -->` regex) was built for the `mapgen` bare-DSL format.

(Note: I-00080 — Draft — covers the mirror-image breakage on the **Docs** page, where `doc_type=diagram` docs holding raw DSL with no fence render as a garbled `<hr>`/`<h2>` mess. I-00081 is scoped to the **Code** page only; no code dependency between them, but the underlying lesson — `doc_type=diagram` has two content shapes in the wild — is shared.)

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Code-page route handlers | `dashboard/routers/code_ui.py` (`code_page`, `code_architecture`, `_clean_diagram_dsl`) | Feed Mermaid a whole Markdown doc → "Syntax error in text" on the Code page |
| Architecture-diagram fragment | `dashboard/templates/fragments/code_architecture_diagram.html` | Assumes a single bare-DSL `<div class="mermaid">`; cannot render a Markdown doc / multiple diagrams |
| Architecture-view fragment | `dashboard/templates/fragments/code_architecture_view.html` | Includes the diagram fragment only when `arch_diagram_dsl` is set — needs to also include it for the new "rendered Markdown" case |
| Client-side Mermaid loader | `dashboard/templates/components/libs/mermaid.html` | (reference only — already handles both `.mermaid` divs and `pre[data-lang="mermaid"]`; no ELK layout loader registered, so `layout: elk` front-matter must be stripped before client render) |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `code_ui.py`: make the `diagram-architecture` rendering format-aware — Markdown-with-fences → rendered HTML (all diagrams, via `_preprocess_mermaid`/`render_markdown`, ELK front-matter stripped); bare-DSL `mapgen` format → unchanged single `<div class="mermaid">` path | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | frontend-impl | `code_architecture_diagram.html` + `code_architecture_view.html`: render the new `arch_diagram_html` when present; keep the `arch_diagram_dsl` path; widen the include guard | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | tests-impl | New `tests/dashboard/test_i00081_code_page_arch_diagram.py` — reproduction (Markdown-format `diagram-architecture` doc → page renders the diagrams cleanly) + regression (bare-DSL format still renders; no Markdown source leaks into a `.mermaid` div; no `layout: elk` reaches the client) | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | code-review-final-impl | Global cross-agent review | — |
| S08..S12 | qv-gate | lint, format, typecheck, unit-tests, integration-tests | — |
| S13 | qv-browser | Browser verification — diagram renders on the Code page, no "Syntax error" box, no new console errors, adjacent flows OK | — |
| S14 | self-assess-impl | Self-assessment via `iw-item-analyze` (project has `self_assess = true`) | — |

Agent slugs: `backend-impl`, `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**:
  - `dashboard/routers/code_ui.py` — add a helper (e.g. `_arch_diagram_html(raw: str) -> tuple[str | None, str | None]` returning `(rendered_html, purpose)`, or two locals) that branches on whether the comment-stripped content contains a ` ```mermaid ` fence:
    - **Markdown-doc case** (` ```mermaid ` present): strip HTML comments; strip a single leading `# …` H1 line (it duplicates the widget's own "Architecture Diagram" `<h3>`); strip the `---\n…\n---` config front-matter from each fenced block (mirror `_clean_diagram_dsl`'s existing strip — the dashboard's client-side Mermaid has no ELK layout loader registered, so a `layout: elk` block makes `mermaid.render()` throw); then `arch_diagram_html = render_markdown(_preprocess_mermaid(content))` (the same pipeline `_render_architecture_html` already uses for the architecture-map). `arch_purpose` is `None` for this case — the `> **Why this diagram?**` blockquotes render inline.
    - **Bare-DSL `mapgen` case**: unchanged — `arch_diagram_dsl = _clean_diagram_dsl(content)`, `arch_purpose` from the `<!-- purpose: … -->` comment, rendered by the existing `<div class="mermaid">` path. (You may keep `arch_diagram_dsl` as a separate context var, or fold it into `arch_diagram_html` by wrapping the DSL in `<pre data-lang="mermaid"><code>{{ dsl | e }}</code></pre>` — but if you fold it, you must keep the rendered output containing `<div class="mermaid">` OR update `tests/dashboard/test_code_page_arch_diagram.py` accordingly; the simpler, lower-risk choice is to keep both vars and not touch that existing test file.)
    - Pass the new context var(s) from **both** `code_page` (→ `project_code.html`) and `code_architecture` (→ `code_architecture_view.html`).
  - `dashboard/templates/fragments/code_architecture_diagram.html` — render `{{ arch_diagram_html | safe }}` inside `.code-diagram-container` when `arch_diagram_html` is set; keep `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>` for the bare-DSL case; keep the `{% if arch_purpose %}` line; keep the `<script>` that calls `window.iwRenderMermaid(container)` (it already handles both `.mermaid` and `pre[data-lang="mermaid"]`). Keep all `format`-filter usage `%`-style (project rule).
  - `dashboard/templates/fragments/code_architecture_view.html` — change the bottom `{% if arch_diagram_dsl %}` include guard to `{% if arch_diagram_dsl or arch_diagram_html %}` (or to `{% if arch_diagram_html %}` if S01 folded everything into one var).
- **Nature of change**: Format-detect the stored `diagram-architecture` doc; render the Markdown-with-fences form through the existing Markdown→HTML+`<pre data-lang="mermaid">` pipeline so every embedded diagram renders client-side; leave the legacy bare-DSL path untouched.

## File Manifest

All files for this work item live under `ai-dev/active/I-00081/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00081_Issue_Design.md` | Design | This document |
| `I-00081_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/I-00081_S01_backend-impl_prompt.md` | Prompt | S01 — `code_ui.py` format-aware diagram rendering |
| `prompts/I-00081_S02_CodeReview_prompt.md` | Prompt | S02 — review S01 |
| `prompts/I-00081_S03_frontend-impl_prompt.md` | Prompt | S03 — diagram + view fragments |
| `prompts/I-00081_S04_CodeReview_prompt.md` | Prompt | S04 — review S03 |
| `prompts/I-00081_S05_tests-impl_prompt.md` | Prompt | S05 — reproduction + regression tests |
| `prompts/I-00081_S06_CodeReview_prompt.md` | Prompt | S06 — review S05 |
| `prompts/I-00081_S07_CodeReview_Final_prompt.md` | Prompt | S07 — global review |
| `prompts/I-00081_S13_BrowserVerification_prompt.md` | Prompt | S13 — browser verification |
| `prompts/I-00081_S14_SelfAssess_prompt.md` | Prompt | S14 — self-assessment |

Reports are created during execution in `ai-dev/active/I-00081/reports/`.

## Test to Reproduce

Write a failing test that demonstrates the bug before fixing it.

**Test-file location**: `tests/dashboard/test_i00081_code_page_arch_diagram.py` — it drives a FastAPI route via the dashboard `client` fixture, so it **must** live under `tests/dashboard/` (the `client` fixture is registered only in `tests/dashboard/conftest.py` / sibling test files — a test in `tests/unit/` or `tests/integration/` fails with `fixture 'client' not found`, see I-00067 and `tests/CLAUDE.md`). Reuse the seeding pattern from the existing `tests/dashboard/test_code_page_arch_diagram.py` (it seeds an `architecture-map` doc + a `diagram-architecture` doc + a completed `CodeIndexJob` and `GET`s `/project/{pid}/code`).

```python
# Markdown-format diagram-architecture doc, as written by the iw-doc-generator skill:
_MD_ARCH_DIAGRAM = (
    "# Demo Project — Architecture Diagram\n\n"
    "<!-- generated: 2026-05-11 -->\n"
    "<!-- doc_job: deadbeef-0000-0000-0000-000000000000 -->\n\n"
    "> **Why this diagram?** Physical topology.\n\n"
    "```mermaid\n---\nconfig:\n  layout: elk\n---\n"
    'flowchart TB\n    DB[(("PostgreSQL"))]\n    DB --> App["App"]\n```\n\n'
    "---\n\n"
    "> **Why this diagram?** Data model.\n\n"
    "```mermaid\n---\nconfig:\n  layout: elk\n---\n"
    "erDiagram\n    PROJECTS ||--o{ WORK_ITEMS : \"\"\n```\n"
)

def test_i00081_markdown_format_diagram_doc_renders_diagrams_not_syntax_error(client, db_session, test_project):
    """FAIL pre-fix (the whole Markdown doc lands inside <div class="mermaid">),
    PASS post-fix (each fenced block becomes a client-renderable <pre data-lang="mermaid">)."""
    # Arrange: seed a completed CodeIndexJob + architecture-map doc + a Markdown-format
    # diagram-architecture doc (content=_MD_ARCH_DIAGRAM).
    # Act:
    html = client.get(f"/project/{test_project.id}/code").text
    # Assert (semantic, not shape):
    #  - status 200
    #  - the doc's two diagrams are present as client-renderable blocks:
    #      html.count('<pre data-lang="mermaid">') >= 2
    #  - their bodies survived: 'flowchart TB' in html and 'erDiagram' in html
    #  - the Markdown chrome did NOT leak into a Mermaid container:
    #      no '<div class="mermaid"># ' / no literal '```mermaid' inside any class="mermaid" element
    #      no '<h1' whose text is "Demo Project — Architecture Diagram" inside the diagram widget
    #  - the ELK front-matter was stripped before client render: 'layout: elk' not in html
    #      (or at minimum not inside any pre[data-lang="mermaid"] block)
```

(Plus regression tests — see TDD Approach.)

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a project whose `diagram-architecture` ProjectDoc is a Markdown document with one or more fenced ```mermaid blocks (the iw-doc-generator format)
When a user opens /project/{id}/code and scrolls to the "Architecture Diagram" widget
Then every embedded Mermaid diagram renders (as client-side-rendered SVG), there is no "Syntax error in text / mermaid version 11.14.0" box, no "Mermaid error: No diagram type detected …" red text, and the raw Markdown source (the `# H1`, the `> blockquotes`, the literal ```mermaid fences) is not dumped into a `.mermaid` element
```

### AC2: Legacy bare-DSL format still works

```
Given a project whose `diagram-architecture` ProjectDoc is the bare-DSL mapgen format ("<!-- purpose: … -->\n---\nconfig:\n  layout: elk\n---\ngraph TD …")
When a user opens /project/{id}/code
Then the diagram still renders exactly once (via the existing `<div class="mermaid">` path), the purpose line still shows above it, and the existing tests in tests/dashboard/test_code_page_arch_diagram.py still pass unchanged
```

### AC3: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/dashboard/test_i00081_code_page_arch_diagram.py passes — including the reproduction test (fails against pre-fix code) and the bare-DSL regression test
```

## Regression Prevention

- The reproduction test seeds the **actual** `iw-doc-generator` Markdown-with-fences shape (multi-`#`/`>`/fence) — so any future regression that re-introduces "feed the whole doc to Mermaid" fails CI.
- A companion regression test seeds the legacy bare-DSL `mapgen` shape and asserts the single-`<div class="mermaid">` path still works — so the fix can't break the legacy format.
- Both content shapes are now documented in this design and in `code_ui.py`'s helper docstring, so the next person who touches the Code-page diagram widget knows `doc_type=diagram` content has two forms in the wild.
- Asserting `'layout: elk' not in html` (or not inside `pre[data-lang="mermaid"]`) locks in the ELK-front-matter strip, since the dashboard's client-side Mermaid bundle has no ELK layout loader registered.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/routers/code_ui.py`
- `dashboard/templates/fragments/code_architecture_diagram.html`
- `dashboard/templates/fragments/code_architecture_view.html`
- `tests/dashboard/test_i00081_code_page_arch_diagram.py`

## TDD Approach

- **Reproducing test**: `test_i00081_markdown_format_diagram_doc_renders_diagrams_not_syntax_error` — seeds a Markdown-format `diagram-architecture` doc; asserts the page renders the embedded diagrams as `<pre data-lang="mermaid">` blocks with their bodies intact and that no Markdown chrome / `layout: elk` leaks into a Mermaid container. Fails against pre-fix code (the whole doc goes into `<div class="mermaid">`), passes after.
- **Unit/route tests**:
  - `test_i00081_bare_dsl_format_still_renders_single_mermaid_div` — seeds the legacy bare-DSL `mapgen` shape; asserts exactly one `<div class="mermaid">` containing `graph TD`, plus the `<!-- purpose: -->` text shown as the purpose line. (Mirrors the existing `test_code_page_arch_diagram.py` coverage but in the I-00081 file so the contract is locked alongside the new behaviour.)
  - `test_i00081_markdown_doc_leading_h1_not_duplicated` — the rendered widget does not show two "Architecture Diagram" titles (the widget's own `<h3>` plus a rendered `<h1>` from the doc); assert the doc's leading `# …` H1 text does not appear as an `<h1>` inside the diagram widget region.
  - `test_i00081_api_code_architecture_endpoint_handles_markdown_doc` — `GET /project/{pid}/api/code/architecture` (the htmx fragment route, `code_architecture()`) with the same Markdown-format seed; assert 200 and the same "diagrams render, no syntax error" properties (this route shares the helper).
  - **Assertion scoping**: when asserting a CSS class is present, use the attribute-scoped form (`'class="mermaid"' in html` or a `class\s*=\s*"[^"]*\bmermaid\b[^"]*"` regex), not the bare substring `"mermaid" in html` — `mermaid` appears in the `<script src=".../mermaid.min.js">` include and in `language-mermaid` (I-00067; see `tests/CLAUDE.md`).
  - **Semantic over shape**: assert the diagram **bodies** survived (`'flowchart TB' in html`, `'erDiagram' in html`), the count of renderable blocks (`>= 2` for a 2-fence doc), and the **absence** of the bug markers (no Markdown source inside a `.mermaid` element, no `layout: elk` reaching the client) — not merely "there's a `<pre>` somewhere".
- **Integration tests**: covered by the same dashboard test file (run under `make test-integration`); no new testcontainer-only behaviour is introduced.

## Notes

- **Why not just extract the first fenced block?** The user asked for the full fix: render *all* of the doc's diagrams (the `iw-ai-core` doc has three — physical topology, work-item lifecycle, DB schema), reusing the existing `_preprocess_mermaid` + `render_markdown` pipeline so they render client-side as `<pre data-lang="mermaid">` blocks (the same path the architecture-map already uses).
- **ELK layout**: the generated diagrams carry `---\nconfig:\n  layout: elk\n---`. The dashboard's client-side Mermaid (`components/libs/mermaid.html`) only calls `mermaid.initialize(...)` — it does **not** call `mermaid.registerLayoutLoaders(...)`, so a `layout: elk` directive makes `mermaid.render()` throw. `_clean_diagram_dsl` already strips this for the bare-DSL path; the Markdown-doc path must do the same per fenced block. S13 (browser verification) must explicitly confirm the diagrams render — if they still error on `layout: elk`, that's the gap.
- **`<br/>` in labels**: `_preprocess_mermaid` substitutes the fenced source verbatim (un-escaped) into `<pre data-lang="mermaid"><code>…</code></pre>`. A `<br/>` inside a Mermaid node label (e.g. `DB[(("PostgreSQL<br/>port 5433"))]`) is then parsed by the browser as a real `<br>` element and disappears from `textContent`, so the label loses its line break. This is a **pre-existing** characteristic of the shared `_preprocess_mermaid` helper (the architecture-map already goes through it) and is out of scope for this incident — the diagram still renders, the label is just on one line. If the implementer wants to fix it cleanly within scope they may HTML-escape the fenced source when emitting the `<pre data-lang="mermaid">` (so `&lt;br/&gt;` round-trips through `textContent` back to `<br/>` for Mermaid), but it is **not required** and must not regress the architecture-map rendering.
- **Routers are thin**: `code_ui.py` already contains `_preprocess_mermaid`, `_clean_diagram_dsl`, `_render_architecture_html` — adding a sibling format-detect helper there is consistent with the existing code. A reviewer may note the "thin routers" rule; the precedent is clear, but if S01 prefers to put the pure helper in a `dashboard/utils/` module or `orch/`-side helper that is acceptable as long as it doesn't pull a DB session into a unit-import chain (`tests/CLAUDE.md` gotcha).
