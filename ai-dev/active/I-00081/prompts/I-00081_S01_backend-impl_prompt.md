# I-00081_S01_backend-impl_prompt

**Work Item**: I-00081 — Code page "Architecture Diagram" widget shows "Syntax error in text — mermaid version 11.14.0" when the `diagram-architecture` doc is the iw-doc-generator Markdown-with-fences form
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
If a task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations and touches no database schema.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00081 --json`. `workflow-manifest.json` is a design-time snapshot.
- `ai-dev/active/I-00081/I-00081_Issue_Design.md` — design document (read **Root Cause Analysis**, **Code Changes**, **Acceptance Criteria**, **Notes** in full first).
- `dashboard/routers/code_ui.py` — the file you change. Key spots: `_clean_diagram_dsl` (~line 35), `_preprocess_mermaid` (~line 77), `_render_architecture_html` (~line 82), `code_page` (~line 91 — see the `arch_diagram_doc` / `arch_purpose` / `arch_diagram_dsl` block ~line 147-156), `code_architecture` (~line 260 — the htmx fragment route, mirrors the same block ~line 270-298).
- `dashboard/templates/fragments/code_architecture_diagram.html` — current rendering: `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>` plus an `{% if arch_purpose %}` line and a `<script>` calling `window.iwRenderMermaid(container)`. Reference only — the template change is S03's job; but understand what context vars it consumes so you pass the right ones.
- `dashboard/templates/components/libs/mermaid.html` — the client-side renderer. Note it only calls `mermaid.initialize({ startOnLoad:false, theme: isDark?'dark':'base', securityLevel:'loose' })` — it does **not** call `mermaid.registerLayoutLoaders(...)`, so a `layout: elk` directive in a diagram makes `mermaid.render()` throw. It handles both `.mermaid` divs and `pre[data-lang="mermaid"]` blocks. Reference only.
- `dashboard/utils/markdown.py` — `render_markdown` (used by `_render_architecture_html`). Reference only — you reuse it, don't change it.
- `orch/rag/mapgen.py` — `mapgen.py:194` (`content = f"<!-- purpose: {purpose} -->\n{dsl}"`) is the *other* writer of slug `diagram-architecture` (the bare-DSL form your bare-DSL branch must keep handling). Reference only.
- `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/rag/CLAUDE.md`, `tests/CLAUDE.md` — conventions.

## Output Files

- `ai-dev/active/I-00081/reports/I-00081_S01_backend-impl_report.md` — step report.
- Modified (expected): `dashboard/routers/code_ui.py`.

## Context

The Code page (`/project/{id}/code`) shows a broken "Architecture Diagram" widget — a wall of red error text ("Mermaid error: No diagram type detected matching given configuration for text: # IW AI Core Platform — Architecture Diagram …") plus "Syntax error in text / mermaid version 11.14.0" boxes — because `code_ui.py` treats the `diagram-architecture` ProjectDoc as a **bare Mermaid DSL string** (`_clean_diagram_dsl()` only strips HTML comments and one leading `---…---` block) and dumps it into `<div class="mermaid">…</div>`. That's correct for the `orch/rag/mapgen.py` form (`<!-- purpose: … -->\n<bare DSL>`), but the doc is **also** written by the `iw-doc-generator` skill as a **full Markdown document** — a `# H1`, `<!-- … -->` comments, several `> **Why this diagram?** …` blockquotes, and several ` ```mermaid ` fenced blocks (each with its own `---\nconfig:\n  layout: elk\n---`). The Markdown blob handed to `mermaid.render()` doesn't parse.

Your job: make `code_ui.py` **format-aware** — render the Markdown-with-fences form through the existing `_preprocess_mermaid` + `render_markdown` pipeline (so every embedded diagram renders client-side as a `<pre data-lang="mermaid">` block, which `iwRenderMermaid` already handles), and leave the legacy bare-DSL path untouched.

## Requirements

### 1. Add a format-aware diagram renderer in `dashboard/routers/code_ui.py`

Add a helper next to `_clean_diagram_dsl` / `_preprocess_mermaid` / `_render_architecture_html` — e.g.:

```python
def _render_arch_diagram(raw: str) -> tuple[str | None, str | None]:
    """Render the stored `diagram-architecture` doc content for the Code page.

    Two content shapes exist in the wild for slug `diagram-architecture`:
      • `orch/rag/mapgen.py` writes a *bare* Mermaid DSL, optionally prefixed by
        a `<!-- purpose: ... -->` comment and a `---\\nconfig:\\n  layout: elk\\n---`
        front-matter block. → render as a single `<div class="mermaid">`.
      • the `iw-doc-generator` skill writes a *Markdown document* — a `# H1`,
        `<!-- ... -->` comments, `> **Why this diagram?** ...` blockquotes, and one
        or more ```mermaid fenced blocks (each with its own `---\\nconfig:\\n  layout: elk\\n---`).
        → render the whole Markdown through `_preprocess_mermaid` + `render_markdown`
        so every fenced block becomes a client-renderable `<pre data-lang="mermaid">`.

    Returns (rendered_html, purpose):
      • Markdown-doc form  → (html_with_pre_mermaid_blocks, None)   # the `> Why` blockquotes carry the purpose inline
      • bare-DSL form      → (None, purpose) and the caller keeps using `_clean_diagram_dsl`
        ...OR fold the bare-DSL form into rendered_html too — your call, but see the test note below.
    """
```

Concretely:

- **Strip HTML comments first** (`<!--.*?-->`, DOTALL), then `.strip()`.
- **Detect the Markdown-doc form**: the comment-stripped content contains a fenced mermaid block — match ` ```mermaid ` at the start of a line (regex `re.search(r"^```mermaid", content, re.MULTILINE)` is fine; don't be fooled by an inline `` `mermaid` `` token).
- **Markdown-doc form**:
  - Drop a single leading `# …` H1 line if present (it duplicates the widget's own "Architecture Diagram" `<h3>`). Drop only the first H1; leave any H2/H3 alone.
  - Strip the `---\n…\n---` config front-matter from **each** fenced mermaid block — mirror what `_clean_diagram_dsl` does for the bare-DSL path. The dashboard's client-side Mermaid has no ELK layout loader registered, so a `layout: elk` block makes `mermaid.render()` throw. (E.g. for each ` ```mermaid `…` ``` ` block, if the block body starts with `---\n`, drop up to and including the next line that is exactly `---`.) Do NOT strip `---` lines that aren't a leading front-matter fence.
  - `rendered = render_markdown(_preprocess_mermaid(content))` — the same pipeline `_render_architecture_html` uses. (You do **not** need `wrap_h2_sections_collapsible` here — the diagram doc has no H2 sections, just blockquotes + fences.)
  - Return `(rendered, None)`.
- **Bare-DSL form** (no fenced block): keep current behaviour — the caller does `arch_diagram_dsl = _clean_diagram_dsl(content)` and `arch_purpose` from the `<!-- purpose: … -->` comment, and the existing `<div class="mermaid">` template path renders it. Either return `(None, purpose)` from the helper and let the caller branch, or return the DSL wrapped as `'<pre data-lang="mermaid"><code>' + html.escape(dsl) + '</code></pre>'` — **but if you fold the bare-DSL form into the rendered-HTML var, you MUST keep the rendered output containing a `class="mermaid"` element OR update `tests/dashboard/test_code_page_arch_diagram.py` (which is NOT in this item's scope)**. The lowest-risk choice: keep two separate context vars (`arch_diagram_html` for the Markdown form, `arch_diagram_dsl` for the bare-DSL form) and don't touch that existing test file. Pick one approach and document it in your report.

### 2. Wire it into both route handlers — `code_page` and `code_architecture`

Both `code_page()` (~line 147) and `code_architecture()` (~line 270) currently do roughly:

```python
arch_diagram_doc = DocService(db).get_doc(project_id, "diagram-architecture")
if arch_diagram_doc and arch_diagram_doc.content:
    m = re.search(r"<!-- purpose: (.*?) -->", arch_diagram_doc.content)
    if m: arch_purpose = m.group(1).strip()
    arch_diagram_dsl = _clean_diagram_dsl(arch_diagram_doc.content)
```

Replace with the format-aware path: produce `arch_diagram_html` (Markdown-doc form) **xor** `arch_diagram_dsl` + `arch_purpose` (bare-DSL form). Add `arch_diagram_html` to **both** template-context dicts (`code_page` → `project_code.html`; `code_architecture` → `code_architecture_view.html`), defaulting to `None`. Do not change `content_html` (that's the separate `architecture-map` doc render via `_render_architecture_html` — leave it exactly as is). Do not change any other context keys.

### 3. Do NOT change

- `_render_architecture_html`, `_preprocess_mermaid`, `dashboard/utils/markdown.py`, `orch/rag/mapgen.py`, `components/libs/mermaid.html`, or any template (S03 owns the templates).
- The `architecture-map` rendering, the `index_status` block, the SSE / index-job routes.
- `_clean_diagram_dsl`'s existing behaviour for the bare-DSL path (you may *call* it from the bare-DSL branch, but don't change what it does).

## Project Conventions

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/rag/CLAUDE.md`. Match the existing helper style in `code_ui.py`. Routers are nominally thin, but `code_ui.py` already houses these small render helpers — a sibling is consistent; do not pull a DB session into a module that unit tests import without a testcontainer (`tests/CLAUDE.md`). `make lint` runs `scripts/check_templates.py` over Jinja2 — irrelevant for a `.py`-only change.

## TDD Requirement

RED → GREEN → REFACTOR. Add a focused test first that exercises `_render_arch_diagram` (or the route) with the Markdown-doc shape and shows it fails against current code (current code feeds the whole blob to `<div class="mermaid">`). Then implement. The full reproduction + regression suite is S05's job — you only need enough to drive your own change; do NOT duplicate S05's file. If you add a quick test, put it where S05 will keep it (`tests/dashboard/test_i00081_code_page_arch_diagram.py`) so it isn't orphaned — or just rely on a `tests/dashboard/`-style check you run locally and let S05 own the committed test file. Either way, your `files_changed` and report must be honest about what test code (if any) you added.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything they report:
1. `make format` — auto-fixes formatting drift; inspect the diff and re-stage.
2. `make typecheck` — zero errors involving the files you touched.
3. `make lint` — zero errors.

Record each in the `preflight` object (`ok` / `fixed` / `skipped:<reason>`). If a tool isn't available in your worktree, STOP and raise a blocker.

## Test Verification (NON-NEGOTIABLE — targeted only)

Run only the targeted dashboard tests for the Code page — e.g.:
```bash
uv run pytest tests/dashboard/test_code_page_arch_diagram.py -v
# plus any test you added under tests/dashboard/test_i00081_code_page_arch_diagram.py
```
Do **NOT** run `make test-integration` or `make test-unit` (full suites) — those are downstream QV gates (S11/S12); running them here blows the step budget (I-00073/S03 post-mortem). Do **NOT** revert source files at runtime to "prove RED". Run `make lint` / `make typecheck` on your touched files. Do not report `tests_passed: true` unless your targeted tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00081",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/routers/code_ui.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Which approach you chose (two context vars vs folded `arch_diagram_html`); the exact new context-var name(s) so S03 and S05 can match; how you strip the leading H1 and the per-block ELK front-matter; whether you added any test code and where."
}
```
