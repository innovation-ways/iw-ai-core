# CR-00044: Markdown viewer for subdirectory docs, sharper per-page help-doc mappings, and favicon route

**Type**: Change Request
**Priority**: Low
**Reason**: Polish on CR-00042 — five of the 22 help popovers fall back to the generic Architecture doc because the `/system/docs/{slug}` route only serves top-level `docs/*.md`; the dashboard also 404s on `/favicon.ico` on every page.
**Created**: 2026-05-10
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This CR does not add, modify, or remove any database migrations.

## Description

CR-00042 added a `/system/docs/{doc_slug}` markdown viewer and centralised the help-popover "Open full docs →" links in a `_SLUG_TO_DOC` dict, but it could only target the flat set of `.md` files in `docs/` — so the five help slugs that have no dedicated top-level doc (`code`, `item_detail`, `projects`, `research`, `search`) all fall back to the generic `IW_AI_Core_Architecture` doc, and `code` in particular lost the intent of pointing at the RAG layer documentation. Separately, every dashboard page logs a single console error: the browser's automatic `GET /favicon.ico` request 404s because the only icon is `/static/favicon.svg`. This CR (a) widens the viewer route to serve documents under subdirectories of `docs/` (and a small curated set of `**/CLAUDE.md` files), (b) retargets the generic help mappings at content-appropriate documents, and (c) adds a `GET /favicon.ico` route.

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules. Key points relevant to this CR:
- Dashboard: FastAPI + Jinja2 templates; routers are thin (`dashboard/routers/`).
- `system.py` exposes routes under the `/system` prefix (`router = APIRouter(prefix="/system")`); CR-00042 added `GET /system/docs/{doc_slug}` there plus `dashboard/templates/pages/system/docs_view.html`.
- `help.py` builds its slug allow-list from the fragment filenames in `dashboard/templates/_partials/help/` and maps each slug to a docs URL via `_SLUG_TO_DOC` (with a fallback to `/system/docs/IW_AI_Core_Architecture`); it injects `docs_link` into each rendered help fragment.
- `GET /health` is registered directly on the app object in `dashboard/app.py` (not via a router); `<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">` is declared in `dashboard/templates/base.html`.
- The `markdown` library (≥3.10.2, with the `toc` extension for heading anchors) is already a dependency — no new dependency needed.
- Append plain CSS to `dashboard/static/styles.css` if `make css` fails (Tailwind toolchain issue, see I-00067) — not expected to be needed here.

## Current Behavior

- `GET /system/docs/{doc_slug}` (`dashboard/routers/system.py`): `doc_slug` is validated against `_DOCS_SLUG_RE = ^[A-Za-z0-9_]+$`, then checked against `_ALLOWED_DOC_SLUGS` (the stems of `docs/*.md`, **non-recursive**), then `docs/{doc_slug}.md` is read and rendered with `markdown(... extensions=["toc","tables","fenced_code"])` into `pages/system/docs_view.html`. The page title is `doc_slug.replace("_", " ")`. Subdirectory documents (`docs/implementation/00_INDEX.md`, `docs/research/*.md`) and `**/CLAUDE.md` files are unreachable; the regex forbids `/` and `.` so any such request 404s.
- `_SLUG_TO_DOC` in `dashboard/routers/help.py` maps 17 of the 22 help slugs to topic-specific docs and 5 (`code`, `item_detail`, `projects`, `research`, `search`) to `/system/docs/IW_AI_Core_Architecture`; only `queue` carries an anchor (`#iw-approve`).
- The dashboard has no `/favicon.ico` route. Browsers request `/favicon.ico` at the site root regardless of the `<link rel="icon">` tag, so every page gets one `GET /favicon.ico → 404` (the single console error visible on every page; harmless).

## Desired Behavior

1. **Subdirectory docs.** `GET /system/docs/{doc_path:path}` serves any markdown document on a precomputed allow-list built once at module load from (a) every file under `docs/**/*.md` (recursive) and (b) an explicit curated list of `**/CLAUDE.md` files worth surfacing (at minimum `orch/rag/CLAUDE.md`; the implementer may include other top-level `CLAUDE.md` files). The allow-list is a `dict` mapping a **URL key** → the document's repo-relative path:
   - for a `docs/` document the URL key is its path **relative to `docs/` with the `.md` suffix dropped** — e.g. `IW_AI_Core_Daemon_Design` → `docs/IW_AI_Core_Daemon_Design.md` (this preserves every flat-form URL CR-00042 served), `implementation/00_INDEX` → `docs/implementation/00_INDEX.md`;
   - for a curated `CLAUDE.md` the URL key is its **repo-relative path including the `.md`** — e.g. `orch/rag/CLAUDE.md` → `orch/rag/CLAUDE.md`.
   A request resolves by looking `doc_path` up in this dict; a miss returns `404`. Path-traversal / escape is additionally guarded by: rejecting any `doc_path` that is empty, starts with `/`, or has a `..` or `.` path component; resolving the mapped file path and confirming it stays inside one of the allowed base directories (`docs/` plus each curated `CLAUDE.md`'s parent dir); and requiring the resolved path to be an existing `.md` file. (The dict membership alone is sufficient; the resolved-path checks are defence-in-depth and the regression tests exercise them.) The rendered page's `<title>` is derived from the document's first level-1 heading (falling back to the file's basename) rather than `slug.replace("_", " ")`.
2. **Sharper help mappings.** `_SLUG_TO_DOC` in `help.py` retargets the generic-Architecture entries at content-appropriate documents: `code` → the RAG layer doc (`/system/docs/orch/rag/CLAUDE.md`), `item_detail` / `research` / `search` → `/system/docs/IW_AI_Core_Dashboard_Design` (with `#anchor` fragments where a stable heading id exists in the rendered output). `projects` stays on `/system/docs/IW_AI_Core_Architecture` (genuinely the right document). Where a target heading id is stable, additional existing entries may gain `#anchor` fragments too. Any anchor placed in `_SLUG_TO_DOC` MUST be verified against the rendered `toc` heading ids of the target document during implementation; if a stable id cannot be confirmed, ship that entry without a fragment. The fallback for an unmapped slug remains `/system/docs/IW_AI_Core_Architecture`.
3. **Favicon route.** `GET /favicon.ico` returns `dashboard/static/favicon.svg` with media type `image/svg+xml` (registered directly on the app in `dashboard/app.py`, next to `GET /health`). No more `/favicon.ico` 404.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `dashboard/app.py` | No `/favicon.ico` route | Adds `GET /favicon.ico` → `FileResponse` of `static/favicon.svg` |
| `dashboard/routers/system.py` | `GET /docs/{doc_slug}`; regex `^[A-Za-z0-9_]+$`; non-recursive allow-list (`docs/*.md` stems); title = `slug.replace("_"," ")` | `GET /docs/{doc_path:path}`; recursive allow-list (`docs/**/*.md` + curated `**/CLAUDE.md`); `..`/escape-resolution traversal guard; title from first H1 |
| `dashboard/routers/help.py` | `_SLUG_TO_DOC`: `code`/`item_detail`/`research`/`search` → `IW_AI_Core_Architecture`; only `queue` has an anchor | `code` → RAG `CLAUDE.md`; `item_detail`/`research`/`search` → `Dashboard_Design` (+ anchors where stable); `projects` unchanged; more anchors where stable |
| `dashboard/templates/pages/system/docs_view.html` | `{% block title %}{{ doc_title }}{% endblock %}` fed by `slug.replace("_"," ")` | Same block, fed by the H1-derived `doc_title` (no template change unless the variable name changes) |
| `dashboard/CLAUDE.md` | Docs-view note describes the `{doc_slug}` form | Note updated for the `{doc_path:path}` form + curated CLAUDE.md set |

### Breaking Changes

None. Existing top-level URLs such as `/system/docs/IW_AI_Core_Daemon_Design` keep resolving (a bare filename stays a URL key in the allow-list map). The new subdirectory form (`/system/docs/orch/rag/CLAUDE.md`, `/system/docs/implementation/00_INDEX`) is purely additive. `GET /favicon.ico` is a new route.

### Data Migration

- None.
- Reversible: yes (revert the merge commit; no data touched).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `app.py` favicon route; `system.py` `{doc_path:path}` + recursive allow-list + traversal hardening + H1 title; `help.py` `_SLUG_TO_DOC` retargeting; `dashboard/CLAUDE.md` note | — |
| S02 | code-review-impl | Per-agent review of S01 — focus on path traversal with the `:path` converter, allow-list correctness, `FileResponse` safety, anchor validity | — |
| S03 | tests-impl | Extend `tests/dashboard/test_system_docs_route.py` (subdir 200, `..`/escape 404, `.ico`→200, H1 title); update `tests/dashboard/test_help_router.py` mapping asserts; add favicon test | — |
| S04 | code-review-impl | Per-agent review of S03 — traversal tests present, mapping/coverage asserts meaningful | — |
| S05 | code-review-final-impl | Cross-agent global review — AC trace, security, no scope creep | — |
| S06 | qv-gate (lint) | `make lint` | — |
| S07 | qv-gate (format) | `make format-check` | — |
| S08 | qv-gate (typecheck) | `make type-check` | — |
| S09 | qv-gate (unit-tests) | `make test-unit` | — |
| S10 | qv-gate (integration-tests) | `make test-integration` (includes `tests/dashboard/`) | — |
| S11 | qv-browser | Help popovers open the right rendered doc; a subdirectory doc renders; `/favicon.ico` returns 200; no regressions | — |
| S12 | self-assess-impl | Post-execution analysis via the iw-item-analyze skill | — |

QV-gate set is the project's standard five (lint, format-check, type-check, unit-tests, integration-tests). `arch-check` / `security-sast` are intentionally omitted: this CR touches only dashboard routers + tests, neither gate has a baseline fingerprint, and a pre-existing violation on `main` (or a missing `bandit`/`pip-audit` in the worktree env) would burn fix cycles on issues unrelated to the change.

No frontend-impl step: the help fragments already render `href="{{ docs_link }}"` (CR-00042); `docs_view.html` needs at most no change (the title variable is populated differently server-side).

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A

### API Changes

- **New endpoints**: `GET /favicon.ico` — returns `static/favicon.svg` (`image/svg+xml`). `GET /system/docs/{doc_path:path}` — supersedes `GET /system/docs/{doc_slug}`; serves `docs/**/*.md` and a curated set of `**/CLAUDE.md`.
- **Modified endpoints**: none beyond the `{doc_slug}` → `{doc_path:path}` widening above.
- **Removed endpoints**: None.

### Frontend Changes

- **New components**: None
- **Modified components**: `dashboard/templates/pages/system/docs_view.html` — only if the title context variable is renamed; otherwise untouched.
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00044_CR_Design.md` | Design | This document |
| `CR-00044_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/CR-00044_S01_backend-impl_prompt.md` | Prompt | S01: favicon route, route widening, help mapping retarget, CLAUDE.md note |
| `prompts/CR-00044_S02_CodeReview_prompt.md` | Prompt | S02: review S01 |
| `prompts/CR-00044_S03_tests-impl_prompt.md` | Prompt | S03: tests |
| `prompts/CR-00044_S04_CodeReview_prompt.md` | Prompt | S04: review S03 |
| `prompts/CR-00044_S05_CodeReview_Final_prompt.md` | Prompt | S05: cross-agent global review |
| `prompts/CR-00044_S11_BrowserVerification_prompt.md` | Prompt | S11: browser verification |
| `prompts/CR-00044_S12_SelfAssess_prompt.md` | Prompt | S12: self-assessment |
| `dashboard/app.py` | Code | `GET /favicon.ico` route |
| `dashboard/routers/system.py` | Code | `{doc_path:path}` route + recursive allow-list + traversal guard + H1 title |
| `dashboard/routers/help.py` | Code | `_SLUG_TO_DOC` retargeting |
| `dashboard/templates/pages/system/docs_view.html` | Template | Title-variable wiring (only if renamed) |
| `dashboard/CLAUDE.md` | Docs | Docs-view route note update |
| `tests/dashboard/test_system_docs_route.py` | Test | Subdir docs, traversal/rejection, flat-form regression, H1 title |
| `tests/dashboard/test_favicon.py` | Test | `GET /favicon.ico` → 200, `image/svg+xml`, SVG bytes |
| `tests/dashboard/test_help_router.py` | Test | Updated `_SLUG_TO_DOC` mapping asserts |

Reports are created during execution in `ai-dev/active/CR-00044/reports/`.

## Acceptance Criteria

### AC1: Subdirectory documents render

```
Given the dashboard is running
When GET /system/docs/orch/rag/CLAUDE.md is requested
Then the response is HTTP 200 with the dashboard chrome and the rendered
  content of orch/rag/CLAUDE.md (e.g. a heading from that file)
And GET /system/docs/implementation/00_INDEX is HTTP 200 with content from
  docs/implementation/00_INDEX.md
```

### AC2: Existing top-level doc URLs still work

```
Given the dashboard is running
When GET /system/docs/IW_AI_Core_Daemon_Design is requested
Then the response is HTTP 200 with content from docs/IW_AI_Core_Daemon_Design.md
  (no regression from CR-00042)
```

### AC3: Path traversal is rejected

```
Given the /system/docs/{doc_path:path} route
When called with a path containing a ".." segment, a leading "/", a path that
  resolves outside the allowed base directories, a non-".md" file, or any path
  not in the precomputed allow-list
Then the route returns HTTP 404 with no file content leaked
```

### AC4: The five generic help mappings point at content-appropriate docs

```
Given the rendered help fragments
When the "Open full docs →" links are inspected for slugs code, item_detail,
  research, search
Then code → /system/docs/orch/rag/CLAUDE.md and item_detail / research / search
  → /system/docs/IW_AI_Core_Dashboard_Design (each optionally with a #anchor),
  and every link returns HTTP 200
And projects still → /system/docs/IW_AI_Core_Architecture
And every #anchor present in _SLUG_TO_DOC matches a heading id in the rendered
  target document
```

### AC5: No more /favicon.ico console error

```
Given the dashboard is running
When GET /favicon.ico is requested
Then the response is HTTP 200 with content type image/svg+xml (the bytes of
  dashboard/static/favicon.svg)
And loading any dashboard page produces zero console errors
```

### AC6: Document page title comes from the first H1

```
Given GET /system/docs/implementation/00_INDEX
When the response HTML <title> is inspected
Then it reflects the document's first level-1 heading (not the literal string
  "implementation/00 INDEX")
```

## Rollback Plan

- **Database**: N/A — no schema changes.
- **Code**: Revert the merge commit. The `{doc_path:path}` route reverts to `{doc_slug}`; `_SLUG_TO_DOC` reverts to the CR-00042 values; `/favicon.ico` 404s again.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: CR-00042 (the `/system/docs/` route and `_SLUG_TO_DOC` it builds on are already merged to `main`).
- **Blocks**: None.

## Impacted Paths

- `dashboard/app.py`
- `dashboard/routers/system.py`
- `dashboard/routers/help.py`
- `dashboard/templates/pages/system/docs_view.html` (in scope as a contingency; only edited if the title context variable is renamed — the design directs S01 to keep the existing `doc_title` key, so no edit is expected)
- `dashboard/CLAUDE.md`
- `tests/dashboard/test_system_docs_route.py`
- `tests/dashboard/test_favicon.py`
- `tests/dashboard/test_help_router.py`

## TDD Approach

- **Unit tests** (`tests/dashboard/test_system_docs_route.py`, extended):
  - `GET /system/docs/orch/rag/CLAUDE.md` → 200, body contains a heading from that file.
  - `GET /system/docs/implementation/00_INDEX` → 200, body contains content from `docs/implementation/00_INDEX.md`.
  - `GET /system/docs/IW_AI_Core_Daemon_Design` → 200 (regression guard for the flat form).
  - `GET /system/docs/../etc/passwd`, `GET /system/docs/..%2f..%2fREADME`, `GET /system/docs/orch/config.py` (non-`.md`), `GET /system/docs/some/unknown/path` → all 404.
  - `<title>` of the `00_INDEX` page reflects the file's first H1.
- **Unit tests** (`tests/dashboard/test_favicon.py` or added to an existing dashboard test module):
  - `GET /favicon.ico` → 200, `content-type` starts with `image/svg+xml`, body equals `dashboard/static/favicon.svg` bytes.
- **Updated tests** (`tests/dashboard/test_help_router.py`):
  - The rendered help fragment for `code` contains `href="/system/docs/orch/rag/CLAUDE.md"` (allowing an optional `#fragment`).
  - The rendered help fragments for `item_detail`, `research`, `search` point at `/system/docs/IW_AI_Core_Dashboard_Design`.
  - `projects` still points at `/system/docs/IW_AI_Core_Architecture`.
  - No rendered fragment contains a hardcoded `/docs/IW_AI_Core` or `/orch/` href (regression guard from CR-00042).

## Notes

- The `markdown` library and its `toc` extension are already dependencies — no new dependency.
- Heading-anchor ids are generated by the `toc` extension by slugifying the heading text content (markdown formatting stripped): `#### \`iw approve\`` → `id="iw-approve"`. Any `#anchor` in `_SLUG_TO_DOC` MUST be confirmed against the rendered ids of the target document during S01; if no stable id can be confirmed, ship that entry without a fragment.
- Keep the curated `**/CLAUDE.md` allow-list small and intentional — these files are agent-instruction documents. `orch/rag/CLAUDE.md` is the one needed for the `code` help link; the implementer may add other top-level `CLAUDE.md` files but should not bulk-add every `CLAUDE.md` in the tree.
- Security: with FastAPI's `:path` converter the matched value can contain `/` and `..`. The guard is, in order: (1) reject any `doc_path` that is empty, starts with `/`, or has a path component equal to `..` or `.`; (2) `mapped = _DOC_URL_MAP.get(doc_path)` — a miss is `404` (this dict-membership check is the real gate); (3) `(_REPO_ROOT / mapped).resolve()` and assert it `is_relative_to` an allowed base dir (`docs/` or each curated `CLAUDE.md`'s parent) — defence-in-depth against symlink / `..` escapes; (4) require the resolved path's `.suffix == ".md"` and `is_file()`. The dict lookup alone is sufficient; steps 3-4 are defence-in-depth and the regression tests exercise them.
- Out of scope: externalising `_SLUG_TO_DOC` to a config file; changing the unmapped-slug fallback behaviour; rewriting help-fragment prose; writing any new documentation content.
