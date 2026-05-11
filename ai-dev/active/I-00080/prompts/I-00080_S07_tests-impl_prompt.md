# I-00080_S07_tests-impl_prompt

**Work Item**: I-00080 — Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware (slow loads, white-on-white diagram labels, blank HTML/PDF tabs)
**Step**: S07
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations and touches no database schema.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00080 --json`.
- `ai-dev/active/I-00080/I-00080_Issue_Design.md` — design document (read **Test to Reproduce**, **Acceptance Criteria**, **TDD Approach** in full).
- `ai-dev/active/I-00080/reports/I-00080_S01_backend-impl_report.md`, `..._S03_frontend-impl_report.md`, `..._S05_api-impl_report.md` — what each implementation step actually did (the enforced colour token from S01; the client-side shim shape from S03; the cache-dir path / helper name / "PDF unavailable" wording from S05). Pull the exact tokens/paths from these reports — assert against them.
- `tests/dashboard/conftest.py` — the `client` fixture and any doc-seeding fixtures. **Tests that drive a FastAPI route or render a Jinja2 template via the `client` fixture MUST live under `tests/dashboard/`** (the `client` fixture is registered only there — a test in `tests/unit/` or `tests/integration/` fails with `fixture 'client' not found`, see I-00067).
- `tests/CLAUDE.md` — test patterns and rules (testcontainers only, never the live DB; `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `create_all()`; `psycopg2`→`psycopg` URL replacement; `monkeypatch.delenv` not `importlib.reload`).
- `dashboard/routers/docs.py`, `dashboard/utils/markdown.py`, `orch/doc_service.py`, `orch/db/models.py` (`DocType`, `ProjectDoc`) — what you're testing.
- Existing dashboard tests touching docs (grep `tests/dashboard/` for `docs` / `ProjectDoc` / `DocService`) — reuse their seeding patterns.

## Output Files

- `ai-dev/active/I-00080/reports/I-00080_S07_tests-impl_report.md` — step report.
- New (expected): `tests/dashboard/test_i00080_docs_diagram_render.py`. (If a pure-`markdown.py` legibility unit test wasn't already added by S01, you may also add one under `tests/unit/` — but check S01's report first; don't duplicate.)

## Context

I-00080 fixes the Docs-page document-rendering pipeline across `dashboard/utils/markdown.py` (S01: deterministic theme + enforced dark label colour on the server-side `mmdc` render), `dashboard/templates/docs_detail.html` / `research_detail.html` (S03: client-side theme-aware diagram render + raw-DSL diagram handling), and `dashboard/routers/docs.py` (S05: `render_mermaid=False` for the interactive panel; version-keyed disk cache on `html_path`/`pdf_path`; 200 + "PDF unavailable" page instead of bare 503; bare-DSL `doc_type=diagram` content normalised into a fenced mermaid block). Your job: a regression test file that **fails against pre-fix code and passes after**, plus tests covering the root-cause paths and edge cases.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Concretely for I-00080:
- BAD: `assert "mermaid" in html` (false-positives on the `<script src=".../mermaid.min.js">` include and on `language-mermaid`).
- GOOD: `assert 'class="mermaid"' in html` or `re.search(r'class\s*=\s*"[^"]*\bmermaid\b[^"]*"', html)` — scoped to an actual element.
- BAD: `assert "<svg" not in html` on the markdown panel (too broad — icon SVGs exist in the chrome).
- GOOD: assert the markdown panel region contains a `pre[data-lang="mermaid"]` **or** `div.mermaid` with the diagram source AND the `<script src="…/mermaid.min.js">` include — i.e. it's set up for *client-side* rendering, not pre-rendered server-side. Optionally, patch `dashboard.routers.docs.render_markdown_with_callouts` and assert it's called with `render_mermaid=False` on `docs_detail` (and with `render_mermaid=True` on `docs_html_view`).
- BAD: `assert resp.status_code != 503`. GOOD: `assert resp.status_code == 200 and b"PDF" in resp.content and b"unavailable" in resp.content.lower()` (or whatever wording S05's report says it used — quote it).
- For the enforced label colour: assert the **specific** token S01 chose (e.g. `b"1e293b" in resp.content` / in the rendered SVG string), not "there's a `style=`".

## Requirements

Create `tests/dashboard/test_i00080_docs_diagram_render.py` with at least these tests (semantic assertions, isolated, deterministic):

### 1. `test_i00080_docs_detail_markdown_panel_renders_diagram_client_side`
Seed a `ProjectDoc` (use the existing seeding fixture/helper) with `content` containing a fenced ` ```mermaid `\n`graph TD; A[Foo]-->B[Bar]`\n` ``` ` block. `GET /project/{pid}/docs/{doc_id}`. Assert: 200; the response includes the mermaid libs `<script>` (`mermaid.min.js`); the markdown region contains a client-renderable mermaid block (`div.mermaid` or `pre[data-lang="mermaid"]` carrying the DSL — scoped class assertion); it does **not** contain an mmdc-produced `<svg ... aria-roledescription="..."` or a `<div class="mermaid-diagram">` wrapper (those are the server-render markers). If feasible, also `monkeypatch` `dashboard.routers.docs.render_markdown_with_callouts` to a spy and assert it was called with `render_mermaid=False`. (Pre-fix: the route called it with `render_mermaid=True` and embedded an mmdc `<svg>` → this fails.)

### 2. `test_i00080_raw_dsl_diagram_doc_renders_as_diagram`
Seed a `ProjectDoc` with `doc_type=DocType.diagram` and `content` = the `orch/rag/mapgen.py` shape: `"<!-- purpose: demo -->\n---\nconfig:\n  layout: elk\n---\ngraph TD\n  A[Foo]-->B[Bar]\n"` (no ` ```mermaid ` fence). `GET /project/{pid}/docs/{doc_id}`. Assert: 200; the markdown region contains a client-renderable mermaid block whose text includes `graph TD` and `A[Foo]` — and does **not** render as a sequence of `<hr>` + setext `<h2>` + `<p>` paragraphs of the DSL (assert the absence of an `<h2>` whose text is `config:` or the literal DSL text appearing as plain `<p>` content; pick a robust signal). (Pre-fix: garbled markdown → this fails.)

### 3. `test_i00080_html_view_caches_to_html_path_keyed_by_version`
Seed a `ProjectDoc` with `html_path=None`. **Make the render deterministic, independent of whether `mmdc` is installed in the worktree**: `monkeypatch` `dashboard.routers.docs.render_markdown_with_callouts` to a spy that returns a fixed HTML string which (a) does **not** contain `language-mermaid` (so S05's "don't cache a degraded render" guard doesn't trip) and (b) contains an unmistakable marker like `<svg id="i00080-fake-diagram">`. `GET /project/{pid}/docs/{doc_id}/html-view`. Assert: 200, `text/html`; the body contains the fake-diagram marker. Re-fetch the doc via `DocService.get_doc` — assert `doc.html_path` is now set, the file exists, and the path contains `v{version}` (use the version the seeded doc has). `GET` the same URL again — assert 200, the body still equals the cached file's bytes, and the spy's call count did **not** increase on the second GET (the cached file was served, not re-rendered). Then add a second assertion path: seed another `ProjectDoc` with a fenced-mermaid `content` and `html_path=None`, monkeypatch `render_markdown_with_callouts` to return HTML that *still contains* `language-mermaid` (simulating mmdc-absent), `GET` its `html-view`, assert 200 — then re-fetch and assert `doc.html_path` is **still None** (the degraded render was not cached).

### 4. `test_i00080_pdf_view_unavailable_returns_200_with_message_not_503`
Seed a `ProjectDoc` with `content` and `pdf_path=None`. `monkeypatch` `dashboard.routers.docs.render_pdf_chromium` to return `None`. `GET /project/{pid}/docs/{doc_id}/pdf-view`. Assert: status **200** (not 503); `text/html` content type; body mentions PDF being unavailable (match the exact wording S05's report records — quote it; e.g. `b"unavailable" in resp.content.lower()`). Then `monkeypatch` `render_pdf_chromium` to return `b"%PDF-1.4 fake"`; `GET` again; assert 200, `application/pdf`, and that the doc's `pdf_path` is now set to an existing file whose path contains `v{version}`.

### 5. `test_i00080_pdf_download_still_works`
`GET /project/{pid}/docs/{doc_id}/pdf` with `render_pdf_chromium` monkeypatched to return `b"%PDF-1.4 fake"`. Assert 200, `application/pdf`, `Content-Disposition: attachment` with the slug+version filename. (Regression guard — the download route's existing behaviour must be untouched except for the diagram-doc normaliser.)

### 6. `tests/unit/test_markdown_mermaid_legibility.py` — `test_render_markdown_with_callouts_enforces_dark_label_colour`
S01 is expected to have already created this file (per its prompt Requirement 2). **Read S01's report first** — if it's present and the assertions match S01's chosen colour token, you don't need to touch it (don't duplicate). If S01's file is missing or the legibility assertion is weak/shape-only, add or strengthen it: call `render_markdown_with_callouts("```mermaid\ngraph TD; A[Foo]-->B[Bar]\n```")`; if the result still contains `language-mermaid`, `pytest.skip("mmdc not available")`; otherwise assert the result contains the specific enforced dark colour token from S01's report (e.g. `1e293b`) and does **not** contain a label `color:#fff` / `color: rgb(255, 255, 255)`. Also assert `render_markdown_with_callouts("```mermaid\n...\n```", render_mermaid=False)` leaves a `language-mermaid` `<pre>` block intact (no `<svg>`).

## Test Verification (NON-NEGOTIABLE — targeted only)

Run **only** the file(s) you created:
```bash
uv run pytest tests/dashboard/test_i00080_docs_diagram_render.py -v
# and, if you added it:
uv run pytest tests/unit/test_markdown_mermaid_legibility.py -v
```
Do **NOT** run `make test-integration` or `make test-unit` — the full suites are S13/S14 QV gates and running them here blows the step budget (I-00073/S03 post-mortem). Do **NOT** revert source files at runtime to "prove RED" — the design author proved RED at design time; your job is GREEN-against-fixed-code + good coverage. Run `make lint` on your new test file.

Do not report `tests_passed: true` unless your targeted tests pass with zero failures. If they fail because an implementation step left something incomplete, report `blocked` with the specific gap — don't weaken the assertions to make them pass.

## Pre-flight Quality Gates

1. `make format`  2. `make typecheck`  3. `make lint` — fix anything they report on your new file(s); record in `preflight`.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "I-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/dashboard/test_i00080_docs_diagram_render.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (Y skipped)",
  "blockers": [],
  "notes": "Which exact tokens/paths/wording you asserted against (cite S01/S05 reports); whether mmdc was available in the worktree; any test you had to mark partial/blocked and why."
}
```
