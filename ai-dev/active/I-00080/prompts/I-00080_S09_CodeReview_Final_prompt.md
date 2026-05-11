# I-00080_S09_CodeReview_Final_prompt

**Work Item**: I-00080 — Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware (slow loads, white-on-white diagram labels, blank HTML/PDF tabs)
**Step**: S09 — Global cross-agent review
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations and no `project_docs` columns. If any step added one, CRITICAL.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00080 --json`.
- `ai-dev/active/I-00080/I-00080_Issue_Design.md` — design (read in full: **Root Cause Analysis**, **Acceptance Criteria AC1–AC5**, **TDD Approach**, **Impacted Paths**).
- `ai-dev/active/I-00080/I-00080_Functional.md` — functional summary.
- All step reports: `ai-dev/active/I-00080/reports/I-00080_S0{1..8}_*_report.md`.
- All changed files across the item: `dashboard/utils/markdown.py`, `dashboard/templates/docs_detail.html`, `dashboard/templates/research_detail.html`, `dashboard/routers/docs.py`, `tests/dashboard/test_i00080_docs_diagram_render.py` (and possibly `tests/unit/test_markdown_mermaid_legibility.py`).
- `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`, `tests/CLAUDE.md`.

## Output Files

- `ai-dev/active/I-00080/reports/I-00080_S09_CodeReview_Final_report.md` — global review report.

## What to verify (integration & completeness)

1. **The three layers fit together**
   - S05 passes `render_mermaid=False` to `render_markdown_with_callouts` for the interactive `docs_detail` panel, AND S03's template includes `components/libs/mermaid.html` + the `pre > code.language-mermaid` → `div.mermaid` shim → so the markdown tab actually renders the diagram client-side. If S05 says `render_mermaid=False` but S03 didn't add the client renderer (or vice-versa), the markdown tab shows raw DSL or nothing — CRITICAL.
   - The `<!-- purpose: … -->` HTML-comment line is stripped in **exactly one** place (S05 server-side is the design's preference). If both strip it, harmless; if neither does, the comment leaks into the Mermaid source and may break the render — HIGH.
   - S01's enforced dark label colour applies to the surfaces that still server-render (`docs_html_view` fallback, `docs_pdf_view`, `docs_pdf`, `docs_export_*`). Confirm those routes still call `render_markdown_with_callouts` with `render_mermaid=True` (they need self-contained SVG) and thus get S01's fix.
   - The bare-DSL `doc_type=diagram` normaliser (S05) is called from **all** Docs render routes (`docs_detail`, `docs_html_view`, `docs_pdf_view`, `docs_pdf`, both `docs_export_*`). A route that renders `doc.content` directly without the normaliser still garbles raw-DSL diagram docs — HIGH.

2. **Caching is version-correct**
   - `html_path` / `pdf_path` cache files embed `v{version}`; `DocService.update_doc` NULLs both on content change; therefore a regenerated doc gets a fresh render. Confirm nothing short-circuits this (e.g. a route that serves a stale `html_path` whose `v{N}` no longer matches `doc.version` — it shouldn't, because `update_doc` NULLed it, but verify the read path checks existence, not just non-None).
   - Cache writes are wrapped so a read-only fs doesn't 500 a GET.

3. **Acceptance criteria** — walk AC1–AC5 against the actual code. AC4 (browser reproduction) is verified by S15, but sanity-check the change set could plausibly satisfy it. AC5: the named test file `tests/dashboard/test_i00080_docs_diagram_render.py` exists, is in S07's `files_changed`, and its tests assert semantic values (not shape) against the *actual* implementation tokens.

4. **Scope discipline** — only the files in **Impacted Paths** changed (plus `ai-dev/active/I-00080/**`). No new DB column, no migration, no change to the doc-generation skills, no edits to `components/libs/mermaid.html` (shared), no edits to the Code page. Anything outside scope → CRITICAL (or, if it's a legitimate latent fix the implementer couldn't avoid, a HIGH with a note that `scope.allowed_paths` must be amended by the operator, not silently expanded).

5. **Lint / format / type clean across the whole change set**
   ```bash
   make lint
   make format-check
   make typecheck
   ```
   New violations → CRITICAL.

6. **Latent-path distrust** — this item makes GET routes write `html_path`/`pdf_path` to the DB (new behaviour on `docs_html_view` / `docs_pdf_view`, mirroring `docs_pdf`). Re-trace: does the dashboard's read-only / db-guard middleware reject a GET that performs a write? (`docs_pdf` already does it, so it should be fine — confirm.) Does `update_doc` on these routes accidentally bump `doc.version` or create a `ProjectDocVersion` snapshot? (It must not — it's only setting a path; `update_doc` only versions when *content* changes.) If either is wrong, HIGH/CRITICAL.

## Test Verification (NON-NEGOTIABLE)

Run the I-00080 test file and a broad unit slice:
```bash
uv run pytest tests/dashboard/test_i00080_docs_diagram_render.py -v
uv run pytest tests/unit/ -k "markdown or doc" -v
```
Report results. Do not run the full integration suite (that's the S14 QV gate).

## Severity Levels & Result Contract

Standard severities. `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE across all of S01–S08.

```json
{
  "step": "S09",
  "agent": "CodeReview_Final",
  "work_item": "I-00080",
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "...", "file": "...", "line": 0, "description": "...", "suggestion": "...", "step_origin": "S0X"}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (Y skipped)",
  "ac_check": {"AC1": "pass|fail|deferred-to-S15", "AC2": "...", "AC3": "...", "AC4": "deferred-to-S15", "AC5": "..."},
  "notes": ""
}
```
