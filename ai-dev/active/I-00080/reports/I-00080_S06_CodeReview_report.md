# I-00080 S06 CodeReview Report

## Reviewed Step: S05 (api-impl)
## Reviewer: CodeReview agent
## Date: 2026-05-11

---

## Files Changed (per `git diff dashboard/routers/docs.py`)

| File | Change |
|------|--------|
| `dashboard/routers/docs.py` | All changes — no other files modified |

---

## Pre-Review Gate

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed (ruff + `scripts/check_templates.py`) |
| `make format-check` | ✅ 670 files already formatted |

No new violations introduced.

---

## Review Checklist

### 1. `docs_detail` no longer shells out to mmdc

**Finding**: ✅ PASS — `docs_detail` (line 103–106) now calls:
```python
normalized_content = _normalize_doc_content_for_render(doc)
content_html = (
    render_markdown_with_callouts(normalized_content, render_mermaid=False)
    ...
)
```
`render_mermaid=False` means no `mmdc` subprocess spawns. The markdown panel contains `language-mermaid` `<pre>` blocks. S03's client-side shim converts these to `<div class="mermaid">` and calls `window.iwRenderMermaid`. Page loads are fast.

### 2. HTML-view caching — version-keyed, cache-write guarded

**Finding**: ✅ PASS

`docs_html_view` (lines 165–183):
- **Fallback branch** (lines 146–185): renders with `_normalize_doc_content_for_render` + `render_mermaid=True` (self-contained inline SVG).
- **Cache-on-success guard** (line 171): writes cache only when `'class="language-mermaid"' not in fallback_html` — this means mmdc succeeded and produced real SVGs. If mermaid rendering fell through (mmdc unavailable), the markdown converter leaves raw `<pre><code class="language-mermaid">` blocks and we skip the cache write. A later request when mmdc is available can succeed and cache properly.
- **Version keying** (line 175): `f"{doc_id}-v{doc.version}.html"` — the filename embeds the doc version.
- **Cache invalidation**: `update_doc` in `orch/doc_service.py:196–198` NULLs `html_path` whenever `content` changes (new hash). Since the cache file is version-keyed, a regenerated doc gets a fresh render. The chain holds correctly.
- **Project binding** (line 133): `project = _get_project_or_404(project_id, db)` — was previously discarding the project variable; now correctly bound.
- **Cache-write failure** (lines 178–183): wrapped in `try/except`, logs warning, returns HTML uncached — no 500.

### 3. PDF-view: no bare 503, cached, graceful fallback

**Finding**: ✅ PASS

`docs_pdf_view` (lines 209–268):
- **When `render_pdf_chromium` returns `None`** (lines 221–252): returns HTTP **200** with a styled inline HTML page ("PDF unavailable" card). Not `HTTPException(503)` — the iframe now shows a meaningful message instead of a blank screen.
- **"PDF unavailable" HTML** (lines 224–251): static text, `system-ui` font, centered card, no user input interpolated — no injection risk.
- **When Chromium succeeds** (lines 254–267): writes to `docs/.generated/{project_id}/{doc_id}-v{doc.version}.pdf` and calls `svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))`. Mirrors `docs_pdf` download pattern exactly.
- **Cache-write failure** (lines 261–266): wrapped in `try/except`, logs warning, returns bytes uncached.

`docs_pdf` download route (lines 299–324): normalisation added (line 302), cache write with version keying (lines 320–324). Unchanged behavior on cache hit (lines 289–298).

### 4. Bare-DSL `doc_type=diagram` normalisation — shared helper, idempotent

**Finding**: ✅ PASS

`_normalize_doc_content_for_render` (lines 29–51):
- Placed **before** `_get_project_or_404` in the file — pure string-operation helper with no DB I/O. ✅
- Only touches `doc_type == DocType.diagram` docs (line 44). ✅
- Only wraps when no `` ```mermaid `` fence is already present (line 47). ✅
- Strips leading `<!-- purpose: ... -->` comment and surrounding blank lines (line 50) before wrapping. ✅
- Idempotent: running it twice on already-normalised content is a no-op. ✅
- No DB I/O. ✅

**Called from**:
- `docs_detail` (line 103) ✅
- `docs_html_view` fallback (line 147) ✅
- `docs_pdf_view` (line 212) ✅
- `docs_pdf` (line 302) ✅
- `docs_export_bundle` `_render_html_for_export` (lines 1049–1056) ✅
- `docs_export_single` `_render_html_for_single` (lines 1090–1094) ✅

The export helpers inline the same logic (since `export_bundle`'s signature passes `content: str` not the doc object) — identical behavior, no duplication of the regex.

**`<!-- purpose -->` consistency between S03 and S05**: S05 strips it server-side once here. S03's client shim's regex finds nothing to strip (no-op, safe). S05's server-side strip is the authoritative one — it covers all surfaces (markdown tab, HTML tab, PDF tab, export). ✅

### 5. No over-reach

**Finding**: ✅ PASS

- `render_markdown_with_callouts` / `render_pdf_chromium` — unchanged. ✅
- Templates unchanged (S03 owns those). ✅
- Routers stay thin — helper is module-level in `docs.py`, not extracted to `dashboard/utils/` (per scope constraint: "helper is small / lives in `dashboard/utils/` if non-trivial" — the helper is 22 lines and purely string-based). ✅

### 6. Latent-path check — `update_doc` called on GET routes

**Finding**: ✅ PASS — No issue

`docs_html_view` (line 177) and `docs_pdf_view` (line 260) call `svc.update_doc` with `html_path`/`pdf_path` on GET routes. This is fine because:
- The dashboard uses a DB write guard (for write actions via `@router.post`), not a guard against GETs writing cache paths.
- `docs_pdf` (the download route) already did exactly this pattern before S05 (line 324 calls `update_doc` with `pdf_path`), and no guard rejects it.
- A GET that writes a cache path is a cache write, not a data mutation — it doesn't go through any write-action gate.

No `write_button_attrs`-style guard is triggered by these calls.

### 7. Conventions / quality / security

**Finding**: ✅ PASS

- `Path` used consistently for filesystem paths (lines 172, 175, 255, 258). ✅
- No hardcoded ports/URLs/credentials. ✅
- "PDF unavailable" HTML (lines 224–251): static text only, no injection. ✅
- `logging.getLogger(__name__).warning` inside `try/except` for cache-write failures — inline import avoids module-level side effects, matches logging style in the file. ✅
- `re` module imported at top of file. ✅
- `DocType` imported from `orch.db.models`. ✅

---

## Test Verification

```
uv run pytest tests/dashboard/ -k docs -v
81 passed, 1 failed, 2 skipped, 639 deselected
```

**1 failure — pre-existing, expected**:
`test_i00074_docs_pdf_view_503_when_chromium_unavailable` — this test asserts the OLD behavior (503 when Chromium unavailable). AC3 of the design explicitly changes this to HTTP **200** + HTML body. The test is now incorrect and needs updating (S07 test-impl scope, not S05). This is documented in S05's own report.

**No new failures introduced.**

---

## Verdict

**PASS** — Zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.

All seven review checklist items pass. Lint and format gates are clean. The one test failure is pre-existing and expected per design intent (AC3 explicitly changes the behavior under test).

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00080",
  "step_reviewed": "S05",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [
    {
      "severity": "LOW",
      "category": "test-expectation-mismatch",
      "file": "tests/dashboard/test_docs_pdf_chromium.py",
      "line": 248,
      "description": "test_i00074_docs_pdf_view_503_when_chromium_unavailable asserts 503 (old behavior). AC3 explicitly changes this to HTTP 200 + HTML body. Test needs updating in S07.",
      "suggestion": "Update the test to expect status_code == 200 and validate the HTML body contains 'PDF unavailable' text."
    }
  ],
  "tests_passed": false,
  "test_summary": "81 passed, 1 failed (pre-existing/expected), 2 skipped",
  "notes": "The failing test is pre-existing — the design explicitly changes the behavior under test (AC3: no bare 503, return HTTP 200 with meaningful HTML). S05 implementation is correct."
}
```