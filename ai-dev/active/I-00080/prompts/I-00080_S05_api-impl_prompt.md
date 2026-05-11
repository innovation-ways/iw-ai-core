# I-00080_S05_api-impl_prompt

**Work Item**: I-00080 — Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware (slow loads, white-on-white diagram labels, blank HTML/PDF tabs)
**Step**: S05
**Agent**: api-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations and touches no database schema. The render cache reuses the **existing** `project_docs.html_path` / `project_docs.pdf_path` columns — keyed to `ProjectDoc.version` (the cache filename embeds `v{version}`; `DocService.update_doc` already NULLs both columns when content changes — `orch/doc_service.py:212-213`). Do **not** add a column.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00080 --json`.
- `ai-dev/active/I-00080/I-00080_Issue_Design.md` — design document (read first; **Root Cause Analysis**, **AC2 / AC3**).
- `ai-dev/active/I-00080/reports/I-00080_S01_backend-impl_report.md` — S01 report (the `markdown.py` theme/label fix).
- `ai-dev/active/I-00080/reports/I-00080_S03_frontend-impl_report.md` — S03 report (the `docs_detail.html` / `research_detail.html` client-side render; tells you whether S03 strips the leading `<!-- purpose --> ` comment in the client shim or expects you to).
- `dashboard/routers/docs.py` — the file you change. Routes to edit: `docs_detail` (~line 64-88), `docs_html_view` (~line 91-133), `docs_pdf_view` (~line 136-174); reference the existing `docs_pdf` download route (~line 177-235) — its disk-cache pattern (`cache_dir = Path(project.repo_root) / "docs" / ".generated" / project_id`, `cache_file = cache_dir / f"{doc_id}-v{doc.version}.pdf"`, `cache_file.write_bytes(...)`, `svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))`) is exactly the shape to mirror.
- `dashboard/utils/markdown.py` — `render_markdown_with_callouts(text, render_mermaid=True)`, `render_pdf_chromium(html_content, timeout=30) -> bytes | None`.
- `orch/doc_service.py` — `DocService.get_doc`, `DocService.update_doc(... html_path=..., pdf_path=...)`; note `update_doc` NULLs `html_path` and `pdf_path` when content changes (lines ~189-213).
- `orch/db/models.py` — `DocType` enum (`...diagram = "diagram"`), `ProjectDoc` (`html_path`, `pdf_path` at lines ~1431-1432).
- `dashboard/CLAUDE.md`, `orch/CLAUDE.md`, `CLAUDE.md` — conventions (routers are thin — keep helpers minimal and inline or in `dashboard/utils/`; never run alembic against the live DB; never `docker compose`).

## Output Files

- `ai-dev/active/I-00080/reports/I-00080_S05_api-impl_report.md` — step report.
- Modified (expected): `dashboard/routers/docs.py`.

## Context

After S01 (server-side `mmdc` render is now theme-neutral + legible) and S03 (the Docs Markdown tab and the Research page render diagrams client-side), the router needs to:
1. Stop server-rendering Mermaid for the **interactive** markdown panel (`docs_detail`) — pass `render_mermaid=False` so `content_html` keeps `language-mermaid` `<pre>` blocks for the client to render. (The HTML-file view and the PDF still server-render — those need self-contained output.)
2. **Cache** the `docs_html_view` and `docs_pdf_view` renders to disk keyed by `ProjectDoc.version`, exactly like `docs_pdf` already caches the download — so the lazy HTML/PDF iframes are only slow once.
3. Make `docs_pdf_view` **never blank** — when `render_pdf_chromium` returns `None`, return a small styled HTML "PDF unavailable" page with HTTP 200 instead of raising `HTTPException(503)`.
4. Make `doc_type=diagram` docs that hold **bare Mermaid DSL** (no ` ```mermaid ` fence — the `orch/rag/mapgen.py` shape) render as a diagram everywhere: when such a doc's content has no ` ```mermaid ` fence, wrap it in one before handing it to `render_markdown_with_callouts` (so the client-side shim picks it up on the markdown tab, and the server-side renderer renders it on the HTML/PDF tabs). Strip a leading `<!-- purpose: … -->` HTML comment line from the wrapped DSL **unless** S03's report says the client shim already handles it (coordinate — but doing it server-side once, for all surfaces, is cleaner; do it server-side and tell S03 you did).

## Requirements

### 1. `docs_detail` — render the interactive markdown panel without server-side Mermaid

In `docs_detail` (`docs.py:77`): change `content_html = render_markdown_with_callouts(doc.content) if doc.content else ""` to pass `render_mermaid=False`. Apply the diagram-doc normalisation from Requirement 4 first (so a bare-DSL `doc_type=diagram` doc still produces a `language-mermaid` block for the client). Result: the page no longer shells out to `mmdc` on load — it returns in milliseconds.

### 2. `docs_html_view` — cache the rendered HTML to `html_path` keyed by version

In `docs_html_view` (`docs.py:91-133`):
- Keep the "prefer the pre-generated branded HTML file on disk" branch (`if doc.html_path and Path(doc.html_path).exists(): return ...`).
- In the fallback branch (no `html_path`): after building `fallback_html` (the `render_markdown_with_callouts(doc.content)` + minimal-styling wrapper — keep `render_mermaid=True` here; this is a self-contained file, so it needs the inline SVG), write it to `Path(project.repo_root)/"docs"/".generated"/project_id/f"{doc_id}-v{doc.version}.html"` (mkdir parents), `svc.update_doc(project_id, doc_id, html_path=str(cache_file))`, and return the bytes. (You'll need the `project` object — `docs_html_view` currently only does `_get_project_or_404(...)` without binding it; bind it. Mirror `docs_pdf`'s `cache_dir` construction exactly.)
  - **Do not cache a degraded render**: if the rendered markdown still contains `language-mermaid` (i.e. `mmdc` was unavailable at request time and the diagram fell through to a raw `<pre>` block), skip the cache write — `svc.update_doc(html_path=...)` — and just return the bytes uncached, so a later request (with `mmdc` available) can produce and cache the real diagram. Only persist `html_path` when the render actually produced the SVG.
- Apply the Requirement-4 diagram-doc normalisation to the content before rendering, same as everywhere else.
- Edge case: if writing the cache file fails (read-only fs, etc.), don't 500 — log and still return the rendered bytes.

### 3. `docs_pdf_view` — cache to `pdf_path`, and never return a blank/bare-503

In `docs_pdf_view` (`docs.py:136-174`):
- Keep the "use cached PDF if available" branch.
- On the generate path: after `pdf_bytes = render_pdf_chromium(html_content)`, **if `pdf_bytes is None`**: return a small styled HTML page (`Response(content=..., media_type="text/html", status_code=200)`) saying the PDF couldn't be generated (Chromium binary not found on this server) with a short hint — **do not raise `HTTPException(503)`** (that renders as a blank iframe). The HTML can be a trivial inline template (system-ui font, centred, neutral colours that read in both light and dark — or just a plain light card; it's inside an iframe, so use its own colours).
- If `pdf_bytes` is not None: write it to `Path(project.repo_root)/"docs"/".generated"/project_id/f"{doc_id}-v{doc.version}.pdf"` (mkdir parents), `svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))`, then return the bytes as `application/pdf`. (Mirror `docs_pdf` lines 225-229. Wrap the cache-write in a try/except — don't 500 on a write failure.)
- Apply the Requirement-4 diagram-doc normalisation to the content before rendering.

### 4. Normalise bare-DSL `doc_type=diagram` content into a fenced mermaid block — shared helper

Add a small module-level helper **in `dashboard/routers/docs.py`** (it's a few string ops, no DB I/O — keep it inline here; `docs.py` is the only file in this step's scope), e.g. `_normalize_doc_content_for_render(doc) -> str`:
- If `doc.doc_type == DocType.diagram` and `doc.content` does **not** already contain a ` ```mermaid ` fence: strip a leading `<!-- … -->` HTML comment line (and surrounding blank lines) from `doc.content`, then wrap the remainder in a ` ```mermaid\n…\n``` ` fence. Optionally prepend the purpose text (extracted from the `<!-- purpose: … -->` comment) as a short italic line above the fence so it's not lost — nice-to-have, not required.
- Otherwise return `doc.content` unchanged.
- Call this everywhere a Docs route renders `doc.content`: `docs_detail`, `docs_html_view`, `docs_pdf_view`, `docs_pdf`, and the two `docs_export_*` routes (`docs.py:957`, `:988` — the `render_html_fn` lambdas; pass the normalised content). Keep it cheap (string ops only, no DB).
- This is intentionally conservative: it only touches `doc_type=diagram` docs, only when there's no fence already, and it's idempotent. It does **not** change what the doc-generation skills store.

### 5. Do not over-reach

- Don't change `docs_pdf` (the download route) except to call the Requirement-4 normaliser — its caching already works.
- Don't change `render_markdown_with_callouts` or `render_pdf_chromium` (S01 owns `markdown.py`).
- Don't touch templates (S03 owns those) — but if S03's report says the client shim does NOT strip the `<!-- purpose -->` comment, your Requirement-4 helper stripping it server-side covers that anyway.
- Routers are thin: the normaliser must stay small (string operations only) — it lives in `docs.py`; do **not** create a new module under `dashboard/utils/` for it (that path is out of this step's scope).

## Project Conventions

Read `dashboard/CLAUDE.md` + `orch/CLAUDE.md` + `CLAUDE.md`. Match existing code in `docs.py`. Never run alembic against the live DB; never `docker compose`. Use `Path` like the existing code does.

## TDD Requirement

RED → GREEN → REFACTOR. The route-level regression tests are S07's job; for your own GREEN check, write/extend a quick `tests/dashboard/` test (or run S07-style assertions ad hoc) confirming: `docs_detail` no longer embeds an mmdc `<svg>`; `docs_html_view` populates `html_path`; `docs_pdf_view` returns 200 + an HTML body when `render_pdf_chromium` is patched to return `None`; a bare-DSL `doc_type=diagram` doc produces a `language-mermaid` block.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting completion, run in order and fix what they report:
1. `make format`
2. `make typecheck`
3. `make lint`

Record each in the `preflight` object. STOP and raise a blocker if a tool is unavailable.

## Test Verification (NON-NEGOTIABLE)

Run the targeted dashboard tests for `docs.py` (`uv run pytest tests/dashboard/ -k docs -v`). Do **NOT** run `make test-integration` (full suite — downstream QV gate). Run `make lint` / `make typecheck` on your touched files. Do not report `tests_passed: true` unless targeted tests pass.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "api-impl",
  "work_item": "I-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/routers/docs.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Where you put the _normalize_doc_content_for_render helper; confirmation you strip the <!-- purpose --> comment server-side (so S03 doesn't need to); the cache-dir path you used; how the 'PDF unavailable' page looks."
}
```
