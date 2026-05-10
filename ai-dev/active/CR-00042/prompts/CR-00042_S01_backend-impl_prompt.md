# CR-00042_S01_backend-impl_prompt

**Work Item**: CR-00042 — Fix Broken "Open full docs" Links in Help Popups
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does not touch migrations. No alembic commands needed.

## Input Files

- `ai-dev/active/CR-00042/CR-00042_CR_Design.md` — full design and acceptance criteria
- `dashboard/routers/system.py` — add new route here
- `dashboard/routers/help.py` — add dict and context injection here
- `dashboard/templates/pages/system/status.html` — reference for system page template pattern
- `dashboard/templates/docs_detail.html` — lines 178-200 — `.prose-doc` CSS class definition to reuse

## Output Files

- `dashboard/routers/system.py` — new `GET /system/docs/{doc_slug}` route appended
- `dashboard/routers/help.py` — `_SLUG_TO_DOC` dict added; `_render_help_fragment` updated to pass `docs_link`
- `dashboard/templates/pages/system/docs_view.html` — new template
- `ai-dev/active/CR-00042/reports/CR-00042_S01_backend-impl_report.md` — step report

## Context

You are implementing the backend half of CR-00042. The problem: every "Open full docs" link in the 22 dashboard help popups returns 404. The links point to `/docs/IW_AI_Core_*.md` paths that do not exist as routes. This step fixes the server side — the route that renders the docs, and the dict that maps each help slug to the right URL. A separate step (S03) will update the HTML templates.

## Requirements

### 1. Add `GET /system/docs/{doc_slug}` to `dashboard/routers/system.py`

The route must:

- Build an allow-list of valid doc slugs **at module load time** by scanning `docs/` for `*.md` files and collecting their stems (e.g., `IW_AI_Core_Daemon_Design`). This is the same pattern used by `_load_allow_list()` in `help.py`. Do NOT hardcode the list — new docs added to `docs/` should automatically become accessible.
- Validate the incoming `doc_slug` against a strict regex **and** against the allow-list. Use `re.compile(r'^[A-Za-z0-9_]+$')` — this prevents any path traversal. Return HTTP 404 if either check fails.
- Construct the file path as `REPO_ROOT / "docs" / f"{doc_slug}.md"`. `REPO_ROOT` should be derived from `Path(__file__).resolve().parent.parent.parent` (three levels up from `dashboard/routers/`). Do NOT use `os.getcwd()` or relative paths.
- Read the file and render it using `markdown.markdown(content, extensions=["toc", "tables", "fenced_code"])`. Import `markdown` at the top of the file. The `toc` extension generates heading `id` attributes needed for anchor deep-links (e.g., `#approve`).
- Return an `HTMLResponse` rendered from `pages/system/docs_view.html` with context: `{"doc_slug": doc_slug, "doc_title": doc_slug.replace("_", " "), "rendered_html": Markup(rendered)}`. Use `markupsafe.Markup` to mark the rendered HTML as safe so Jinja2 does not double-escape it. `markupsafe` is already available (it is a FastAPI/Jinja2 transitive dep).
- The route response class is `HTMLResponse`. Use `request: Request` as the first parameter (needed for `request.app.state.templates`).

Example skeleton (adjust imports as needed):

```python
_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
_DOCS_SLUG_RE = re.compile(r"^[A-Za-z0-9_]+$")
_ALLOWED_DOC_SLUGS: set[str] = set()

def _load_doc_allow_list() -> set[str]:
    if not _DOCS_DIR.is_dir():
        return set()
    return {p.stem for p in _DOCS_DIR.glob("*.md") if p.is_file()}

_ALLOWED_DOC_SLUGS = _load_doc_allow_list()

@router.get("/docs/{doc_slug}", response_class=HTMLResponse)
def system_docs_view(doc_slug: str, request: Request) -> HTMLResponse:
    ...
```

### 2. Add `_SLUG_TO_DOC` dict to `dashboard/routers/help.py`

Add the following mapping near the top of the module (after the existing `_HELP_FRAGMENTS_DIR` constant):

```python
_SLUG_TO_DOC: dict[str, str] = {
    "all_active":   "/system/docs/IW_AI_Core_Daemon_Design",
    "batch_detail": "/system/docs/IW_AI_Core_Daemon_Design",
    "batches":      "/system/docs/IW_AI_Core_Daemon_Design",
    "code":         "/system/docs/IW_AI_Core_Architecture",
    "config":       "/system/docs/IW_AI_Core_Tech_Stack",
    "containers":   "/system/docs/IW_AI_Core_Worktree_Isolation",
    "coverage":     "/system/docs/IW_AI_Core_Tech_Stack",
    "docs":         "/system/docs/IW_AI_Core_Dashboard_Design",
    "history":      "/system/docs/IW_AI_Core_CLI_Spec",
    "item_detail":  "/system/docs/IW_AI_Core_Architecture",
    "job_detail":   "/system/docs/IW_AI_Core_Daemon_Design",
    "jobs":         "/system/docs/IW_AI_Core_Daemon_Design",
    "keep_alive":   "/system/docs/IW_AI_Core_Daemon_Design",
    "projects":     "/system/docs/IW_AI_Core_Architecture",
    "quality":      "/system/docs/IW_AI_Core_Tech_Stack",
    "queue":        "/system/docs/IW_AI_Core_CLI_Spec#iw-approve",
    "research":     "/system/docs/IW_AI_Core_Architecture",
    "running":      "/system/docs/IW_AI_Core_Daemon_Design",
    "search":       "/system/docs/IW_AI_Core_Architecture",
    "status":       "/system/docs/IW_AI_Core_DB_Setup",
    "tests":        "/system/docs/IW_AI_Core_Tech_Stack",
    "worktrees":    "/system/docs/IW_AI_Core_Daemon_Design",
}
```

**Important**: The `toc` extension slugifies the heading **text content** (markdown formatting stripped). `docs/IW_AI_Core_CLI_Spec.md` has the heading `#### \`iw approve\``, which renders as `<h4 id="iw-approve">` — hence `#iw-approve` above (NOT `#approve`). The `batches`/`batch_detail` entries currently carry **no** fragment because the Daemon Design headings produce long, unstable slugs (`## 4. BatchManager — Per-Project Processing` → `id="4-batchmanager--per-project-processing"`); if you want a deep-link there, render the doc, read the actual heading id, and only then add a fragment. When in doubt, omit the fragment — the link still resolves to the correct document.

### 3. Update `_render_help_fragment` in `help.py` to pass `docs_link`

Change `_render_help_fragment` to accept a `docs_link: str` parameter and pass it to the Jinja2 template render call:

```python
def _render_help_fragment(slug: str, templates: Jinja2Templates, docs_link: str) -> str:
    template_name = f"_partials/help/{slug}.html"
    fragment = templates.get_template(template_name)
    return fragment.render(docs_link=docs_link)
```

In `get_help_fragment`, look up the docs_link from `_SLUG_TO_DOC`. If the slug is not in the dict (future-proofing), fall back to `"/system/docs/IW_AI_Core_Architecture"`.

```python
docs_link = _SLUG_TO_DOC.get(slug, "/system/docs/IW_AI_Core_Architecture")
html_content = _render_help_fragment(slug, templates, docs_link)
```

### 4. Create `dashboard/templates/pages/system/docs_view.html`

Create a Jinja2 template that:
- Extends `base.html`
- Sets `{% block title %}{{ doc_title }}{% endblock %}`
- Does NOT set `{% block page_help_slug %}` (no help button on a help target page)
- Renders the `rendered_html` inside a `.prose-doc` container

Copy the `.prose-doc` inline `<style>` block from `docs_detail.html` (lines ~181-200) verbatim — do not attempt a Tailwind recompile.

Include a simple back button above the content:

```html
<a href="javascript:history.back()" class="text-sm text-muted-foreground hover:text-foreground mb-4 inline-block">← Back</a>
```

The content area:

```html
<div class="prose-doc max-w-4xl mx-auto px-4 py-8">
  {{ rendered_html }}
</div>
```

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md` for FastAPI/Jinja2 patterns. Match the style of existing routes in `system.py`. No new imports are needed in `app.py` — the new route is added to the existing `system` router (prefix `/system`).

## TDD Requirement

Follow TDD (Red-Green-Refactor). Write a test file `tests/dashboard/test_system_docs_route.py` with at minimum:
1. `GET /system/docs/IW_AI_Core_Daemon_Design` → 200, body contains rendered HTML (not raw `#` markdown)
2. `GET /system/docs/nonexistent_slug` → 404
3. `GET /system/docs/..%2F..%2Fetc%2Fpasswd` → 404

Write these tests RED first, then implement GREEN.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting complete:
1. `make format` — auto-fixes formatting
2. `make typecheck` — zero errors on touched files
3. `make lint` — zero errors

## Test Verification

Run only your newly created test file:
```bash
uv run pytest tests/dashboard/test_system_docs_route.py -v
```

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00042",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/system.py",
    "dashboard/routers/help.py",
    "dashboard/templates/pages/system/docs_view.html",
    "tests/dashboard/test_system_docs_route.py",
    "ai-dev/active/CR-00042/reports/CR-00042_S01_backend-impl_report.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
