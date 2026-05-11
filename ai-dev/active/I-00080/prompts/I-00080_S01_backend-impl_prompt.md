# I-00080_S01_backend-impl_prompt

**Work Item**: I-00080 — Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware (slow loads, white-on-white diagram labels, blank HTML/PDF tabs)
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

- **Runtime step state** — prefer `uv run iw item-status I-00080 --json`. `workflow-manifest.json` is a design-time snapshot.
- `ai-dev/active/I-00080/I-00080_Issue_Design.md` — design document (read first; especially **Root Cause Analysis** and **AC1**).
- `dashboard/utils/markdown.py` — the file you change. Key functions: `render_markdown_with_callouts` (~line 422), `_render_mermaid_blocks` (~line 371), `_render_mermaid_to_svg` (~line 268), `_render_mermaid_mmdc` (~line 291), `_render_mermaid_kroki` (~line 339), and the module-level `_PUPPETEER_CONFIG` / `_PLAYWRIGHT_CHROME` / `_MERMAID_CODE_RE` constants near the top.
- `dashboard/templates/components/libs/mermaid.html` — the *client-side* renderer the Code page uses (`mermaid.initialize({ theme: isDark ? 'dark' : 'base', … })`). Reference only — your job is to make the *server-side* `mmdc` output theme-neutral and legible, not to touch this file.
- `orch/rag/module_gen.py` — defines `_MERMAID_CLASSDEF` (the `classDef` lines injected into generated diagrams). Reference only — useful to understand what colours nodes carry.
- `CLAUDE.md`, `dashboard/CLAUDE.md` — conventions.

## Output Files

- `ai-dev/active/I-00080/reports/I-00080_S01_backend-impl_report.md` — step report.
- Modified (expected): `dashboard/utils/markdown.py`.

## Context

The Docs page renders Mermaid diagrams server-side: `render_markdown_with_callouts` → `_render_mermaid_blocks` → `_render_mermaid_to_svg` → `_render_mermaid_mmdc` shells out to `npx @mermaid-js/mermaid-cli` with only `-b white` and a puppeteer config — **no `-t <theme>`, no `-c <config>`**. The resulting inline SVG uses Mermaid's default `htmlLabels: true`, so node/edge label text lives in `<foreignObject> <div>` elements that do not enforce a colour; embedded into the dashboard page in dark mode, those labels inherit the page `color` and render **white on the white (`-b white`) diagram box** — invisible. Confirmed on the live dashboard: a label `<div>` computes `color: rgb(255, 255, 255)`.

Your job: make the **server-side `mmdc` render produce a self-contained, theme-neutral, legible diagram** — a light/neutral background with dark, readable labels and edges — so the SVG looks correct no matter where it is later embedded (dark dashboard page, standalone HTML file, PDF). The caching of these renders is handled separately in S05 (router layer, keyed to `ProjectDoc.version`); the *interactive* Docs markdown tab is moved to client-side rendering in S03/S05. Your change is the safety net for the surfaces that still server-render (the HTML-file view, the PDF, the export ZIP, the `iw docs-export` CLI).

## Requirements

### 1. Pin a deterministic Mermaid theme + enforce legible label colours on the `mmdc` render — `dashboard/utils/markdown.py`

In `_render_mermaid_mmdc` (and/or `_render_mermaid_to_svg`):

- Pass `mmdc` an explicit theme + config so the output is deterministic and not dependent on the embedding page. Options (pick whichever is cleanest and verifiably works against the project's bundled `@mermaid-js/mermaid-cli`):
  - Add `-t default` (Mermaid's `default` theme has dark `#333`-ish text on light fills) and write a small `mermaid` config file passed via `-c`/`--configFile` that sets `htmlLabels: false` (so labels become plain SVG `<text>` with a `fill` colour the SVG controls) **or** sets `themeVariables` with explicit dark `primaryTextColor` / `textColor` / `nodeTextColor` / `lineColor` and a light `background`.
  - Keep `-b white` (or switch to a neutral very-light background — `#ffffff` is fine; the point is the diagram box is light and self-contained).
- Belt-and-braces: after `mmdc` produces the SVG, in `_render_mermaid_blocks` wrap it so its labels cannot inherit a near-white page `color` — e.g. emit `<div class="mermaid-diagram" style="overflow-x:auto;margin:1rem 0;background:#ffffff;color:#1e293b;border-radius:6px;padding:0.5rem;">…svg…</div>` and/or inject a tiny `<style scoped>` that forces `.mermaid-diagram svg foreignObject div, .mermaid-diagram svg .nodeLabel, .mermaid-diagram svg text { color:#1e293b !important; fill:#1e293b; }`. The wrapper `<div>` already exists at `markdown.py:386-388` — extend its inline style; only add the `<style>` if the wrapper colour alone doesn't win the cascade (test it).
  - **Important**: do not break the kroki fallback (`_render_mermaid_kroki`) or the raw-`<pre>` fallback (when both renderers fail, `_replace` returns `match.group(0)` — keep that). The kroki SVG should get the same wrapper treatment so it's legible too.
- Do not change the public signature of `render_markdown_with_callouts` (it already has `render_mermaid: bool = True`). Do not change `render_markdown`.
- No new module-level network calls, no new subprocess timeouts longer than the existing ones.

### 2. Verify the output is legible

Write a new unit test file at **`tests/unit/test_markdown_mermaid_legibility.py`** (this exact path is pre-declared in `workflow-manifest.json:scope.allowed_paths` — do not put it elsewhere; no FastAPI/template dependency → `tests/unit/`, not `tests/dashboard/`) that:
- Calls `render_markdown_with_callouts` on a short markdown string containing a ` ```mermaid ` block (e.g. `graph TD; A[Foo]-->B[Bar]`).
- Skips itself cleanly if `mmdc` is not available in the environment (e.g. `pytest.skip("mmdc not available")` when the render falls through to the raw `<pre>` — detect by checking whether the result still contains `language-mermaid`). The CI worktree has node + the bundled CLI, but be defensive.
- When mmdc *did* render: asserts the output contains the **specific enforced dark colour token** you chose (e.g. `1e293b` appears in the wrapper style or a `themeVariables` value) and does **not** contain a bare white label colour. Assert the *specific* token — not just "there is a `style=` attribute". (S07 will add the dashboard-route-level regression tests; this one locks the util-level contract.)

### 3. (No caching here)

Caching of rendered HTML/PDF is S05's job (router layer, keyed to `ProjectDoc.version` via `html_path` / `pdf_path`). Do **not** add a module-level dict cache in `markdown.py` — it would not be version-aware and would leak across docs.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Match existing code in `markdown.py`. Keep Jinja2 `format`-filter rule in mind if you touch any templates (you shouldn't here). `make lint` runs `scripts/check_templates.py` — irrelevant for a `.py`-only change but don't add template strings that violate it.

## TDD Requirement

RED → GREEN → REFACTOR. Write the markdown-render legibility test first (it should fail against the current `markdown.py` — current output has no enforced dark colour token), then implement, then refactor.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything they report:
1. `make format` — auto-fixes formatting drift; inspect the diff and re-stage.
2. `make typecheck` — zero errors involving the files you touched.
3. `make lint` — zero errors.

Record each in the `preflight` object of your result contract (`ok` / `fixed` / `skipped:<reason>`). If a tool isn't available in your worktree, STOP and raise a blocker.

## Test Verification (NON-NEGOTIABLE)

Run only the targeted tests for the code path you changed — e.g.:
```bash
uv run pytest tests/unit/ -k markdown -v
```
Do **NOT** run `make test-integration` or `make test-unit` (full suites) — those are downstream QV gates. Run `make lint` / `make typecheck` on your touched files. Do not report `tests_passed: true` unless your targeted tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/utils/markdown.py", "tests/unit/test_markdown_mermaid_legibility.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Which theme/config approach you used; whether the wrapper <div> colour alone won the cascade or you also needed a <style> block; whether mmdc was available in the worktree to exercise the legibility test."
}
```
