# I-00081 S02 Code Review Report

## Summary

Reviewed S01 (backend-impl) changes to `dashboard/routers/code_ui.py` and the new test file `tests/dashboard/test_i00081_code_page_arch_diagram.py`.

**Verdict: PASS — zero mandatory findings.**

S01 correctly adds the format-aware `_render_arch_diagram()` helper and wires `arch_diagram_html` into both `code_page` and `code_architecture` route contexts. The 2 failing integration tests are expected — they fail because the template (`code_architecture_view.html`) only includes the diagram fragment when `arch_diagram_dsl` is set, not when `arch_diagram_html` is set. That is S03's job. The bare-DSL regression test passes. The unit tests for `_render_arch_diagram` pass. No lint/format/typecheck violations.

---

## Files Reviewed

| File | Change |
|------|--------|
| `dashboard/routers/code_ui.py` | Added `_render_arch_diagram()` helper (lines 91–157); wired `arch_diagram_html` into `code_page` (lines 222–225) and `code_architecture` (lines 354–357) |
| `tests/dashboard/test_i00081_code_page_arch_diagram.py` | New 290-line test file with 2 unit tests + 3 route tests |

---

## Pre-Review Lint & Format Gate

- `make lint`: ✅ All checks passed (ruff + template checker)
- `make format-check`: ✅ All 672 files already formatted
- `make typecheck`: ✅ No issues in 240 source files

No new violations introduced by S01.

---

## Review Checklist

### 1. Does S01 actually fix the bug? (Markdown path)

The `_render_arch_diagram()` helper (lines 91–157) correctly branches on the presence of a ` ```mermaid ` fence at line-start (`re.search(r"^```mermaid", stripped, re.MULTILINE)`):

- **HTML comments stripped**: `re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)` (line 116)
- **Single leading `# …` H1 dropped**: `re.sub(r"^#\s+[^\n]+\n+", "", stripped, count=1)` (line 126) — only the first H1, not every `#` line ✅
- **ELK front-matter stripped from each fenced block**: inner function `_strip_elk_fm()` (lines 131–136) anchored to `block_body.startswith("---\n")` + finds `"\n---"` — correctly mirrors `_clean_diagram_dsl`'s existing behavior
- **Per-block processing**: `fence_pat.sub(replacer, stripped)` (line 146) iterates all fenced blocks and removes their ELK front-matter
- **Pipeline**: `render_markdown(_preprocess_mermaid(stripped))` (line 148) — same pipeline `_render_architecture_html` uses for the architecture-map
- **Returns**: `(rendered, None, None)` so `arch_diagram_html = rendered`, `arch_diagram_dsl = None`, `arch_purpose = None` ✅

### 2. Bare-DSL path preserved

When no fence is detected (line 151–157):
- `purpose` extracted from `<!-- purpose: ... -->` via `re.search()` on the raw (un-stripped) string ✅
- `_clean_diagram_dsl(raw)` called ✅ (strips HTML comments + ELK front-matter from the optional leading `---` block)
- Returns `(None, dsl, purpose)` ✅

The existing `<div class="mermaid">` template path is completely untouched. The bare-DSL regression test (`test_bare_dsl_format_still_renders_single_mermaid_div`) passes, confirming exactly one `<div class="mermaid">` with `graph TD`, no `<pre data-lang="mermaid">`.

### 3. Both routes wired

- `code_page()` (lines 222–225): calls `_render_arch_diagram(arch_diagram_doc.content)` and adds `arch_diagram_html` to the template context ✅
- `code_architecture()` (lines 354–357): same call, same context variable ✅
- Both pass all three vars (`arch_diagram_html`, `arch_diagram_dsl`, `arch_purpose`) ✅
- `content_html` (the separate `architecture-map` render) is untouched ✅

### 4. No out-of-scope edits

Only `dashboard/routers/code_ui.py` (+ new test file) changed. Verified by reading the full diff:
- `_preprocess_mermaid`: unchanged ✅ (S01 uses it, doesn't modify it)
- `_clean_diagram_dsl`: unchanged ✅
- `dashboard/utils/markdown.py`: unchanged ✅
- `orch/rag/mapgen.py`: unchanged ✅
- `components/libs/mermaid.html`: unchanged ✅
- No templates modified (S03 scope) ✅

### 5. No latent regressions / unit-import trap

- `_render_arch_diagram` is a pure function with no DB session in its import chain ✅
- Regex for fenced block detection is anchored: `re.search(r"^```mermaid", stripped, re.MULTILINE)` (line 120) — not a bare `"```mermaid" in content` ✅
- H1 strip removes only the *first* `# …` line: `count=1` (line 126) ✅
- ELK strip is anchored: `block_body.startswith("---\n")` (line 132) + `"\n---"` boundary — won't eat `---` inside a label ✅
- No `str.format`-style Jinja2 `format` filter usage (`.py` only) ✅
- No hardcoded paths/ports/URLs/secrets ✅

### 6. Conventions & security

Matches `CLAUDE.md` + `dashboard/CLAUDE.md` conventions. Clean, well-documented helper with a thorough docstring explaining both content shapes. No security concerns.

---

## Test Results

```
tests/dashboard/test_i00081_code_page_arch_diagram.py
  test_render_arch_diagram_markdown_format          PASSED ✅
  test_render_arch_diagram_bare_dsl                  PASSED ✅
  TestI00081MarkdownDiagramFormat
    test_markdown_format_doc_renders_diagrams_not_syntax_error  FAILED (expected — S03 not done)
    test_api_code_architecture_endpoint_handles_markdown_doc    FAILED (expected — S03 not done)
    test_bare_dsl_format_still_renders_single_mermaid_div       PASSED ✅

tests/dashboard/test_code_page_arch_diagram.py (existing, regression net)
  TestI00055DoubleDiagram (4 tests)                            ALL PASSED ✅

Total: 7 passed, 2 expected-fail (blocked on S03 template update)
```

The 2 failures are correct and expected. The root cause is in `code_architecture_view.html` line 47: `{% if arch_diagram_dsl %}` — it has no branch for when `arch_diagram_html` is set (the Markdown-doc path). S03 will add `{% if arch_diagram_html %}` or widen the condition to `{% if arch_diagram_dsl or arch_diagram_html %}`. Once S03 updates the template, the 2 currently-failing tests will pass.

The existing `test_code_page_arch_diagram.py` tests (bare-DSL / mapgen format) continue to pass — no regression.

---

## Context Variables for S03

S01 correctly passes these from both routes:

| Variable | Type | Set when |
|----------|------|----------|
| `arch_diagram_html` | `str \| None` | Markdown-doc format (iw-doc-generator) — full rendered HTML with `≥3` `<pre data-lang="mermaid">` blocks |
| `arch_diagram_dsl` | `str \| None` | Bare-DSL format (mapgen) — raw Mermaid DSL for `<div class="mermaid">` path |
| `arch_purpose` | `str \| None` | Bare-DSL only — extracted from `<!-- purpose: ... -->` |

---

## Mandatory Fix Count

**0** — No CRITICAL, HIGH, or MEDIUM_FIXABLE findings.

---

## Notes

- The `replacer` inner function (lines 141–144) emits ` ```mermaid\n{cleaned_body}``` ` — a well-formed fenced block that `_preprocess_mermaid` correctly converts to `<pre data-lang="mermaid"><code>…</code></pre>`.
- The Markdown path does not call `wrap_h2_sections_collapsible` (unlike `_render_architecture_html`) — confirmed correct since the diagram doc has no H2 sections, only blockquotes + fences.
- S01 explicitly chose to keep two separate context vars (`arch_diagram_html` and `arch_diagram_dsl`) rather than folding the bare-DSL path into HTML, which correctly avoids needing to touch `tests/dashboard/test_code_page_arch_diagram.py` (not in scope).

---

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00081",
  "step_reviewed": "S01",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": false,
  "test_summary": "7 passed, 2 failed (expected — blocked on S03 template update), 4 existing regression tests passed",
  "findings": [],
  "notes": "Two route-integration tests fail because code_architecture_view.html only includes the diagram fragment for arch_diagram_dsl, not arch_diagram_html. This is S03's scope. Unit tests for _render_arch_diagram pass. Bare-DSL regression test passes. No lint/format/typecheck violations."
}
```