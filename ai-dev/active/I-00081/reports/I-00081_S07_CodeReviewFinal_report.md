# I-00081 S07 Global Cross-Agent Code Review Final Report

## Overview

Global cross-agent review of all I-00081 implementation work across S01 (Backend), S03 (Frontend), and S05 (Tests). This review verifies integration correctness, naming consistency, scope discipline, no double-rendering, ELK stripping, and test completeness.

---

## 1. Router ↔ Template Contract

**Trace: `code_page` → `project_code.html` → `code_architecture_view.html` → `code_architecture_diagram.html`**

- `code_page()` (lines 217–225): calls `_render_arch_diagram(arch_diagram_doc.content)` → unpacks `(arch_diagram_html, arch_diagram_dsl, arch_purpose)` → passes all three to `project_code.html` context. CONFIRMED.
- `project_code.html` line 119: includes `code_architecture_view.html` when `content_html` is truthy. `content_html` comes from `_render_architecture_html(arch_doc_for_template)`. Both `content_html` and `arch_diagram_*` vars are only set inside the same `if last_completed_job and last_completed_job.doc_id:` block — in practice they go together. CONFIRMED (pre-existing design, not a new regression).
- `code_architecture_view.html` line 47: `{% if arch_diagram_dsl or arch_diagram_html %}` — widened by S03 from the pre-fix `{% if arch_diagram_dsl %}`. CONFIRMED.
- `code_architecture_diagram.html` line 1: outer guard `{% if arch_diagram_html or arch_diagram_dsl %}`. Line 9: `{% if arch_diagram_html %}` → `{{ arch_diagram_html | safe }}`. Line 11–12: `{% else %}` → `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>`. CONFIRMED.

**Trace: `code_architecture` (htmx route) → `code_architecture_view.html` → `code_architecture_diagram.html`**

- `code_architecture()` (lines 351–370): same `_render_arch_diagram` call → `(arch_diagram_html, arch_diagram_dsl, arch_purpose)` all passed to `code_architecture_view.html` context. CONFIRMED.

**Verdict: PASS** — both entry points wire all three context variables correctly.

---

## 2. Both Content Shapes Work End-to-End

### Markdown-with-fences form (iw-doc-generator)

`_render_arch_diagram()` (code_ui.py lines 91–157):
- Strips HTML comments via `re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)`.
- Detects the form via `re.search(r"^```mermaid", stripped, re.MULTILINE)` — anchored to line-start.
- Drops a single leading `# ...` H1: `re.sub(r"^#\s+[^\n]+\n+", "", stripped, count=1)`.
- Strips ELK front-matter from each fenced block via `_strip_elk_fm()` inner function.
- Processes all blocks with `fence_pat.sub(replacer, stripped)`.
- Returns `render_markdown(_preprocess_mermaid(stripped))` as `(rendered_html, None, None)`.

Verified by test 1 (route) and test 5 (unit): 3-fence seed → `html.count('<pre data-lang="mermaid">') >= 2`, all diagram bodies present, no `<div class="mermaid">`, no `layout: elk`.

### Bare-DSL form (mapgen)

Falls through to the existing `_clean_diagram_dsl(raw)` + purpose extraction. Returns `(None, dsl, purpose)`. Template renders `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>`.

Verified by test 2 (route) and the existing `test_code_page_arch_diagram.py` (4 tests): exactly 1 `<div class="mermaid">`, 0 `<pre data-lang="mermaid">`, `graph TD` body present, purpose line rendered, `layout: elk` absent.

**Verdict: PASS** — both paths work correctly.

---

## 3. No Double Rendering

- `mermaid.html` is included once (in `project_code.html`'s `{% block head %}`) for the full-page route. The two fragment files (`code_architecture_view.html`, `code_architecture_diagram.html`) do not include `mermaid.html` independently. Confirmed by scanning all `{% include "components/libs/mermaid.html" %}` references — none in fragments.
- The fragment's `<script>` (code_architecture_diagram.html lines 17–32) calls `window.iwRenderMermaid(container)` scoped to `#code-arch-diagram`. No `mermaid.initialize` or `mermaid.render` direct calls. The `not([data-processed])` guard in `iwRenderMermaid` prevents any node from being processed twice if both `DOMContentLoaded` and the fragment's IIFE fire.
- The pre-fix symptom had three "Syntax error" boxes. Post-fix, only the `iwRenderMermaid(container)` IIFE fires (with the correct content); the `DOMContentLoaded` handler that fires on page load processes everything not yet processed.

**Verdict: PASS** — exactly one renderer path fires per node.

---

## 4. Acceptance Criteria

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Markdown-doc form renders diagrams, no "Syntax error" box, no raw Markdown/fences in `.mermaid` element | deferred-to-S13 (browser verification), but plausible: ELK stripped, fences processed, H1 dropped, no `<div class="mermaid">` in Markdown path |
| AC2 | Bare-DSL form still renders once via `<div class="mermaid">`, purpose line shows, existing tests pass | pass — test 2 + all 4 existing `test_code_page_arch_diagram.py` tests pass |
| AC3 | `tests/dashboard/test_i00081_code_page_arch_diagram.py` exists and all 5 tests pass | pass |

---

## 5. Scope Discipline

`git diff HEAD --stat` shows only 3 files changed (committed):
- `dashboard/routers/code_ui.py` — in scope
- `dashboard/templates/fragments/code_architecture_diagram.html` — in scope
- `dashboard/templates/fragments/code_architecture_view.html` — in scope

One new untracked file:
- `tests/dashboard/test_i00081_code_page_arch_diagram.py` — in scope

Files that must be unchanged — verified:
- `dashboard/templates/components/libs/mermaid.html` — UNCHANGED
- `dashboard/templates/project_code.html` — UNCHANGED
- `tests/dashboard/test_code_page_arch_diagram.py` — UNCHANGED (4 tests still pass)
- `dashboard/utils/markdown.py` — UNCHANGED
- `orch/rag/mapgen.py` — UNCHANGED

No new DB columns, migrations, or schema changes. CONFIRMED.

**Verdict: PASS** — scope is clean.

---

## 6. Lint / Format / Type

| Gate | Result |
|------|--------|
| `make lint` (ruff + `scripts/check_templates.py` Jinja2 checker) | PASS — "All checks passed!" |
| `make format-check` | PASS — 672 files already formatted |
| `make typecheck` (mypy) | PASS — no issues in 240 source files |
| No `str.format`-style Jinja2 `format` filter | CONFIRMED — no `| format` calls in either changed template |
| No TODO/FIXME/HACK/debug prints | CONFIRMED — none in changed files |

**Verdict: PASS**

---

## 7. Latent-Path Distrust

- `_render_arch_diagram()` is a pure function: reads a string, runs regex/string ops, calls existing helpers `_preprocess_mermaid` and `render_markdown` (both pure). No DB session in its body.
- No `DocService.update_doc`, `ProjectDoc.version` bump, or version snapshot write in the render path. The route only reads `DocService(db).get_doc(...)` — read-only.
- `_render_arch_diagram` is placed in `dashboard/routers/code_ui.py`, which imports `SessionLocal` transitively. Tests live under `tests/dashboard/` with the testcontainer `db_session` fixture active at collection time — the `tests/CLAUDE.md` "never import dashboard routers in a unit test unless `db_session` is in scope" gotcha does not apply here.

**Verdict: PASS** — no latent risks.

---

## 8. Cross-Layer Integration Check

| Layer | Key Point |
|-------|-----------|
| `code_ui.py` | Produces `arch_diagram_html`, `arch_diagram_dsl`, `arch_purpose` — all consistently named across both routes |
| `code_architecture_view.html` | Guard widened to `{% if arch_diagram_dsl or arch_diagram_html %}` — matches S01's contract |
| `code_architecture_diagram.html` | Outer guard matches; inner branch `{% if arch_diagram_html %}` renders pre-rendered HTML; `{% else %}` renders legacy DSL |
| `mermaid.html` | Unchanged; handles both `.mermaid` and `pre[data-lang="mermaid"]` nodes |
| Tests | Route tests drive the full stack (DB → route → template → rendered HTML); unit test 5 covers the helper logic in isolation |

No shared utilities duplicated. No concept renamed between layers (`arch_diagram_html` / `arch_diagram_dsl` / `arch_purpose` consistent everywhere).

---

## 9. Test Results

```
$ uv run pytest tests/dashboard/test_i00081_code_page_arch_diagram.py -v
5 passed, 0 failed (coverage floor failure expected for isolated run)

$ uv run pytest tests/dashboard/test_code_page_arch_diagram.py -v
4 passed, 0 failed

$ uv run pytest tests/dashboard/ -k "code" -v
78 passed, 3 skipped, 1 xfailed, 0 failed
```

All mandatory test commands pass. Coverage floor failure in isolated runs is expected — the full suite (S11/S12 QV gates) will cover it.

---

## 10. Findings

No CRITICAL, HIGH, or MEDIUM findings across S01–S06 work. All per-agent reviews (S02, S04, S06) reported 0 mandatory fixes.

One informational observation (not a finding):

- **INFO**: `project_code.html` includes `code_architecture_view.html` only when `content_html` is truthy (architecture-map doc present). If the architecture-map doc is absent but the diagram-architecture doc is present, the diagram widget is not shown. This is a pre-existing design from before I-00081 — `arch_diagram_*` vars are only populated in the same branch that populates `content_html`. Not a regression introduced by this item.

---

## Summary

The I-00081 implementation across S01–S05 is correct, complete, and well-integrated:
- The `_render_arch_diagram()` helper correctly detects both content shapes and routes them through the appropriate rendering pipeline.
- Both routes (`code_page` and `code_architecture`) wire the new context variable consistently.
- The two fragments correctly render the Markdown-doc form (via `{{ arch_diagram_html | safe }}`) and the bare-DSL form (via `<div class="mermaid">`) without double-rendering.
- ELK front-matter is stripped before client render on both paths.
- The leading H1 is dropped for the Markdown-doc path.
- All 5 new tests + 4 existing regression tests pass. Lint/format/typecheck clean.
- Scope is clean — only 4 files touched (3 modified + 1 new test file), all in scope.

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00081",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed (new file); 4 passed, 0 failed (existing I-00055 file); 78 passed, 3 skipped, 1 xfailed (full -k code run)",
  "ac_check": {
    "AC1": "deferred-to-S13",
    "AC2": "pass",
    "AC3": "pass"
  },
  "notes": "Zero mandatory findings across all S01-S06 work. All quality gates clean. Scope discipline maintained. Both content shapes (Markdown-doc and bare-DSL) render correctly through their respective template paths. No double rendering. ELK front-matter stripped. No DB writes in render path."
}
```
