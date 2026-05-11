# I-00081 S05 tests-impl Report

## Summary

Rewrote `tests/dashboard/test_i00081_code_page_arch_diagram.py` to match the
S05 prompt's required test names and to add the missing test 3
(`test_i00081_markdown_doc_leading_h1_not_duplicated`). Tests assert
**specific values** (counts of `<pre data-lang="mermaid">` blocks, presence
of diagram bodies, *absence* of raw-Markdown leakage / ELK front-matter)
rather than shape — per the assertion-strength rules in
`skills/iw-ai-core-testing/SKILL.md` and `tests/CLAUDE.md`.

## Files Changed

| File | Change |
|------|--------|
| `tests/dashboard/test_i00081_code_page_arch_diagram.py` | Rewrote to exactly the 5 test names the prompt requires; added the leading-H1 dup test; tightened assertions (page-wide `'<div class="mermaid">' not in html` on the Markdown-doc path, zero `<pre data-lang="mermaid">` from the bare-DSL path, region-scoped `<h1>` check). |

## Rendered-output markers asserted against (cited from S01 + S03 reports)

* **Markdown-doc path → `<pre data-lang="mermaid">` blocks** (S01 report §
  "What Was Implemented", `_render_arch_diagram` → "every fenced block becomes
  a client-renderable `<pre data-lang="mermaid">`"; S03 report § "Context-var
  names matched" — `arch_diagram_html` is pre-rendered HTML containing
  `<pre data-lang="mermaid">` blocks).
* **Bare-DSL path → exactly one `<div class="mermaid">`** (S03 report:
  "Kept the existing `{% else %}` fallback that renders
  `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>` for the legacy
  bare-DSL form"; S01 report: `arch_diagram_dsl` is the raw DSL string).
* **Two context vars, not folded** (S01 report § "Approach: Two separate
  context variables") — drove the test for "no `<div class="mermaid">` at all
  in the Markdown-doc path" and "no `<pre data-lang="mermaid">` at all in
  the bare-DSL path" (test isolates the arch-map content from fences).
* **ELK front-matter stripped** (S01 report § `_strip_elk_fm` and
  `_clean_diagram_dsl`) — drove the `"layout: elk" not in html` assertions
  on every path.
* **Leading H1 dropped** (S01 report § "Markdown-doc form … Drops a single
  leading `# …` H1 line") — drove test 3's region-scoped `<h1` and H1-text
  assertions.

## Was test 5 (pure-helper unit test) included?

**Yes.** S01 exposed `_render_arch_diagram` at module level in
`dashboard.routers.code_ui` (per S01 report; confirmed by import in the
existing test file). The dashboard test module already loads
`db_session` via the testcontainer conftest, so the `SessionLocal` side
effect in `dashboard.routers.code_ui`'s import chain is safe (see the
`tests/CLAUDE.md` gotcha about unit tests importing dashboard routers).
Test 5 covers both branches of the helper with a single test call per
branch, asserting the tuple contract from the S01 report.

## Existing test file untouched

`tests/dashboard/test_code_page_arch_diagram.py` was not modified — still
covers the I-00055 double-diagram path with the legacy bare-DSL form.
Confirmed by running both files together (9 passed).

## Pre-flight Quality Gates

| Check | Result |
|-------|--------|
| `make format` | ok — 672 files already formatted |
| `make typecheck` | ok — no issues in 240 source files |
| `make lint` | ok (initially flagged one `assert a and b` on the new file; split into two single-condition asserts per ruff `PT018`) |

## Test Results

### Targeted (the new file):

```
$ uv run pytest tests/dashboard/test_i00081_code_page_arch_diagram.py -v --no-cov
collected 5 items
test_i00081_markdown_format_diagram_doc_renders_diagrams_not_raw_markdown PASSED
test_i00081_bare_dsl_format_still_renders_single_mermaid_div                PASSED
test_i00081_markdown_doc_leading_h1_not_duplicated                          PASSED
test_i00081_api_code_architecture_endpoint_handles_markdown_doc             PASSED
test_i00081_render_arch_diagram_helper_detects_format                       PASSED
========================= 5 passed in 5.91s =========================
```

### Regression (the existing I-00055 file):

```
$ uv run pytest tests/dashboard/test_code_page_arch_diagram.py -v --no-cov
collected 4 items
test_code_page_renders_exactly_one_diagram                              PASSED
test_architecture_map_content_has_no_trailing_diagram_section           PASSED
test_diagram_architecture_doc_renders_as_bottom_diagram                 PASSED
test_strip_helper_is_applied_to_arch_map_content                        PASSED
========================= 4 passed in 6.02s =========================
```

### Combined: 9 passed, 0 failed, 0 skipped.

I did NOT run `make test-integration` / `make test-unit` (those are S11/S12
QV gates with their own budgets — running them in S05 would blow this
step's budget, per I-00073/S03 post-mortem).

## Notes / Observations

* Test 3's region extraction uses a deterministic slice from
  `id="code-arch-diagram"` to the next `</script>` boundary — the upgrade
  script in `code_architecture_diagram.html` reliably terminates the
  widget region without leaking into unrelated `<h1>`s on the page
  (the arch-map content's `# Architecture Map` does produce an `<h1>`
  outside the widget, which is why a page-wide `<h1` check would be
  wrong).
* Test 2 keeps the arch-map content fence-free so
  `html.count('<pre data-lang="mermaid">') == 0` is an unambiguous
  proof that the bare-DSL template branch ran (vs. the Markdown-doc
  branch leaking through).
* Test 1 asserts the *strongest* page-wide invariant for the
  Markdown-doc path — `'<div class="mermaid">' not in html` — because
  the Markdown path never produces that element and the arch-map render
  uses `<pre data-lang="mermaid">` only.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "I-00081",
  "completion_status": "complete",
  "files_changed": ["tests/dashboard/test_i00081_code_page_arch_diagram.py"],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed (0 skipped) on the new file; 4 passed on the existing I-00055 file (untouched).",
  "blockers": [],
  "notes": "Asserted against the markers documented in S01 + S03 reports: `<pre data-lang=\"mermaid\">` blocks for the Markdown-doc path (no `<div class=\"mermaid\">` at all); single `<div class=\"mermaid\">` for the bare-DSL path (no `<pre data-lang=\"mermaid\">` from the diagram doc); `layout: elk` stripped on every path; leading `# H1` dropped (no `<h1>` inside the `#code-arch-diagram` widget region). S01 exposed `_render_arch_diagram` so test 5 is included. tests/dashboard/test_code_page_arch_diagram.py confirmed untouched and green."
}
```
