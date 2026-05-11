# I-00080 S05 API-impl Report

## What was done

All changes are in `dashboard/routers/docs.py`.

### 1. `_normalize_doc_content_for_render` helper (new)

A module-level helper that normalises bare-DSL `doc_type=diagram` docs into fenced mermaid blocks:

```python
def _normalize_doc_content_for_render(doc: Any) -> str:
    if doc.doc_type != DocType.diagram:
        return doc.content or ""
    content = doc.content or ""
    if "```mermaid" in content:
        return content
    stripped = re.sub(r"^<!--[\s\S]*?-->\s*", "", content, count=1).lstrip("\n")
    return f"```mermaid\n{stripped}\n```"
```

Conservative and idempotent: only touches `doc_type==DocType.diagram` docs, only wraps when no fence is already present, strips a leading `<!-- purpose: … -->` HTML comment (and surrounding blank lines) so Mermaid never sees it.

This is placed **before** `_get_project_or_404` in the file — it's a pure string-operation helper with no DB I/O.

### 2. `docs_detail` — no server-side Mermaid

Changed `render_markdown_with_callouts(doc.content)` → `_normalize_doc_content_for_render(doc)` with `render_mermaid=False`. The S03 client-side shim handles diagram rendering. Page loads are now millisecond-fast.

### 3. `docs_html_view` — disk cache keyed by `ProjectDoc.version`

- Now binds `project` from `_get_project_or_404` (was discarding it).
- On the fallback path: applies `_normalize_doc_content_for_render` before rendering.
- **Cache-on-success**: after building `fallback_html`, only writes `html_path` when the result does NOT contain a raw `language-mermaid` block (i.e. `mmdc` or Kroki succeeded). This prevents a degraded render from being cached.
- Cache path: `Path(project.repo_root) / "docs" / ".generated" / project_id / f"{doc_id}-v{doc.version}.html"` — mirrors `docs_pdf` exactly.
- On cache-write failure: logs and returns bytes uncached (no 500).
- Result: repeat views are instant (disk cache hit); first view is still slow once (one-time render).

### 4. `docs_pdf_view` — disk cache + graceful "PDF unavailable" page

- Now applies `_normalize_doc_content_for_render` before rendering.
- When `render_pdf_chromium` returns `None`: returns HTTP 200 with a styled inline HTML page explaining Chromium is unavailable. **Not a 503** — the iframe now shows a meaningful message instead of a blank screen.
- When Chromium succeeds: writes to `Path(project.repo_root) / "docs" / ".generated" / project_id / f"{doc_id}-v{doc.version}.pdf"` and calls `svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))` — mirrors the `docs_pdf` download pattern.
- Cache-write failure: logs and returns bytes uncached.

### 5. `docs_pdf` (download route) — normalisation only

Added `_normalize_doc_content_for_render` call in the on-the-fly render branch (cache hit path unchanged). No caching changes needed — already cached correctly.

### 6. Export routes — normalisation

- `docs_export_bundle`: replaced the lambda with `_render_html_for_export` helper that normalises before rendering.
- `docs_export_single`: replaced the lambda with `_render_html_for_single` helper that normalises before rendering.
  (Both live as local functions in each route to avoid touching `export_bundle`'s signature, which is shared with the CLI.)

## Design decisions

- **Where the normaliser lives**: module-level in `docs.py`, before `_get_project_or_404`. Not in `dashboard/utils/` per scope constraint.
- **`<!-- purpose -->` stripping**: done server-side once here, so S03's client shim finds nothing to strip (no-op regex — safe). This is the cleaner approach since it covers all surfaces (markdown tab, HTML tab, PDF tab, export).
- **Cache-degradation guard**: the `language-mermaid` check is the right sentinel — the fallback HTML uses the self-contained render path (`render_mermaid=True`), so if mermaid rendering failed (mmdc unavailable), the markdown converter leaves `<pre><code class="language-mermaid">` blocks. We skip the cache write when we see that, so a later request (mmdc available) can produce and cache the real diagram.
- **`logging.getLogger(__name__).warning` inside the try/except**: inline import to avoid introducing module-level side effects; matches the logging import style already in the file.

## Preflight

| Check | Result |
|-------|--------|
| `make format` | ok — 670 files already formatted |
| `make typecheck` | ok — no issues in 240 source files |
| `make lint` | ok — all checks passed (ruff + `scripts/check_templates.py`) |

## Test results

Targeted dashboard tests (`tests/dashboard/ -k docs`):
- **81 passed, 1 failed, 2 skipped**
- The 1 failure is **pre-existing and intentional**: `test_i00074_docs_pdf_view_503_when_chromium_unavailable` was written to assert the old (pre-fix) 503 behaviour. Our requirement 3 explicitly changes this to HTTP 200 + HTML body. The test needs updating by the test-impl agent in S07 (or as a follow-up) — not by this step.

## Notes

- The `docs_pdf_view` "PDF unavailable" HTML page uses system-ui font, a centered light card, and inline CSS — readable in both light and dark mode (it's rendered inside an iframe, so uses its own colour context).
- The cache-dir path used is `docs/.generated/{project_id}/` — the same pattern as the existing `docs_pdf` cache. This directory is in `.gitignore` already (generated content).
- The normaliser is intentionally conservative: it only modifies `doc_type=diagram` content that has no fence, and it's idempotent — running it twice on already-normalised content is a no-op.
