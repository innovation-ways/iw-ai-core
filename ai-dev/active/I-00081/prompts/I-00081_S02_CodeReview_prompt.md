# I-00081_S02_CodeReview_prompt

**Work Item**: I-00081 — Code page "Architecture Diagram" widget shows "Syntax error in text — mermaid version 11.14.0"
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations. If S01 added an alembic file or touched `orch/db/`, that is a CRITICAL finding (out of scope).

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00081 --json`.
- `ai-dev/active/I-00081/I-00081_Issue_Design.md` — design (read **Root Cause Analysis**, **Code Changes**, **Acceptance Criteria**, **Notes** in full first).
- `ai-dev/active/I-00081/reports/I-00081_S01_backend-impl_report.md` — S01 report (note which approach S01 chose and the new context-var name(s)).
- All files in S01's `files_changed` (expected: `dashboard/routers/code_ui.py`, possibly a test file under `tests/dashboard/`).
- `dashboard/templates/fragments/code_architecture_diagram.html`, `dashboard/templates/fragments/code_architecture_view.html`, `dashboard/templates/components/libs/mermaid.html` — to confirm the context vars S01 produces match what the templates will consume (S03 will adjust the templates, but S01 must already be passing the right keys).

## Output Files

- `ai-dev/active/I-00081/reports/I-00081_S02_CodeReview_report.md` — review report.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on S01's `files_changed`, report only (fix nothing):
```bash
make lint
make format-check
```
Any NEW violation in the changed files (not present on `main` before S01) → a CRITICAL finding with `"category":"conventions"`, file, line, exact code+message.

## Review Checklist

1. **Does S01 actually fix the bug?** For the Markdown-with-fences `diagram-architecture` content, the page must no longer hand the whole Markdown blob to a `class="mermaid"` element. Verify: HTML comments stripped; a single leading `# …` H1 dropped; the `---\n…\n---` config front-matter stripped from **each** fenced `mermaid` block (so `layout: elk` doesn't reach client-side Mermaid — `components/libs/mermaid.html` registers no ELK layout loader); content rendered via `_preprocess_mermaid` + `render_markdown` so each fence becomes a `<pre data-lang="mermaid">`. If the H1 is kept → MEDIUM_SUGGESTION (duplicate title). If the ELK front-matter is NOT stripped → HIGH (the fix won't hold — diagrams still error client-side).
2. **Bare-DSL path preserved.** The `orch/rag/mapgen.py` form (`<!-- purpose: … -->\n<bare DSL>`, optionally with a leading `---\n…\n---`) must still render via the existing `<div class="mermaid">` path with the purpose line above it. If S01 folded everything into one rendered-HTML var, confirm the bare-DSL branch's output still contains a `class="mermaid"` element **or** that `tests/dashboard/test_code_page_arch_diagram.py` would still pass (that file is NOT in scope — if it would now fail, that's a CRITICAL: either revert to two vars or the item's scope must be amended by the operator, not silently expanded).
3. **Both routes wired.** Both `code_page` and `code_architecture` (the htmx fragment route) must produce the new context var(s) and pass them to their respective templates (`project_code.html` / `code_architecture_view.html`), with a sane default (`None`). `content_html` (the separate `architecture-map` render) must be untouched. No other context keys changed.
4. **No out-of-scope edits.** Only `dashboard/routers/code_ui.py` (+ optionally a `tests/dashboard/` test file) changed. `_render_architecture_html` / `_preprocess_mermaid` / `dashboard/utils/markdown.py` / `orch/rag/mapgen.py` / `components/libs/mermaid.html` / any template must be unchanged (templates are S03). Anything else → CRITICAL.
5. **No latent regressions / unit-import trap.** The new helper is a pure function (no DB session in its import chain that would break a `tests/unit/` import — `tests/CLAUDE.md`). The regex for detecting a fenced block is anchored (`^```mermaid` multiline), not a bare `"```mermaid" in content` that could match an inline token. The H1 strip removes only the *first* H1, not every `# `-prefixed line. The per-block front-matter strip doesn't eat `---` lines that are content (e.g. an `erDiagram` body never has `---`, but a `flowchart` could have a `---` in a label — be sure the strip is anchored to "block body starts with `---\n`").
6. **Conventions / security.** Matches `CLAUDE.md` + `dashboard/CLAUDE.md`; no hardcoded paths/ports/URLs; no secrets; no new long subprocess calls; no `str.format`-style Jinja `format` filter (n/a — `.py` only).

## Test Verification (NON-NEGOTIABLE)

Run the targeted Code-page dashboard tests (e.g. `uv run pytest tests/dashboard/test_code_page_arch_diagram.py -v` and any I-00081 test S01 added). Report results accurately. Do not run the full integration suite.

## Severity Levels & Result Contract

Standard severities (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW). `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE.

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00081",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "...", "file": "...", "line": 0, "description": "...", "suggestion": "..."}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
