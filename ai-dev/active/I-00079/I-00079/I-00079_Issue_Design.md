# I-00079: Empty-state CTA links point to non-existent `/docs/<name>.md` route (404)

**Type**: Issue
**Severity**: Low
**Created**: 2026-05-11
**Reported By**: User report (noticed the broken "How to design an item →" link on the empty Queue page)
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.) This item touches no Docker state.

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.) This item adds no migrations and touches no database schema.

## Description

Every dashboard empty-state panel has a primary call-to-action link (e.g. "How to design an item →" on an empty Queue) that points at `/docs/<DocName>.md`. No route matches that path — the dashboard serves docs at `/system/docs/<DocName>` (no `.md` suffix) — so clicking the link lands the user on `{"detail":"Not Found"}` (HTTP 404). Seven empty-state CTA links across six page templates are affected (the Queue page has two such panels — one for the approved-items list, one for the drafts list).

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules (in particular: Tailwind CSS is prebuilt — a pure href-string change needs no `make css`; `make lint` runs `scripts/check_templates.py` over Jinja2 templates; routers are thin).

## Steps to Reproduce

1. Open the dashboard (`/`), pick any project, and go to its **Queue** page while the queue has no approved items and no drafts (e.g. the `cv` project).
2. In the "No work items yet" empty-state panel, click the **"How to design an item →"** button.
3. The browser navigates to `…/docs/IW_AI_Core_CLI_Spec.md`.

**Expected**: The CLI-spec documentation page renders (the same page reached from the help popover's "Open full docs" link, i.e. `/system/docs/IW_AI_Core_CLI_Spec#iw-approve`).

**Actual**: The page shows the JSON body `{"detail":"Not Found"}` with HTTP 404 — `/docs/<name>.md` matches no FastAPI route (`docs_global.py` registers only the exact path `/docs` and `/api/docs/search`; the markdown viewer lives at `/system/docs/{doc_path:path}` and expects the key **without** the `.md` suffix).

The full set of affected empty-state CTAs (the originally-reported Queue link plus six more):

| Template | Line | CTA label | Broken `primary_href` |
|----------|------|-----------|------------------------|
| `dashboard/templates/pages/project/queue.html` | 97 | "How to design an item →" | `/docs/IW_AI_Core_CLI_Spec.md` |
| `dashboard/templates/pages/project/queue.html` | 197 | "How to design an item →" | `/docs/IW_AI_Core_CLI_Spec.md` |
| `dashboard/templates/pages/project/history.html` | 139 | "How execution works →" | `/docs/IW_AI_Core_Architecture.md` |
| `dashboard/templates/pages/project/batches.html` | 137 | "About batches →" | `/docs/IW_AI_Core_Daemon_Design.md#batches` |
| `dashboard/templates/pages/system/all_active.html` | 72 | "Daemon overview →" | `/docs/IW_AI_Core_Daemon_Design.md` |
| `dashboard/templates/docs_library.html` | 129 | "Doc catalogue →" | `/docs/implementation/00_INDEX.md` |
| `dashboard/templates/research_library.html` | 149 | "Open the catalogue →" | `/docs/implementation/00_INDEX.md` |

## Browser Evidence

Captured against the running dashboard (`http://localhost:9900`), `cv` project Queue page:

- `ai-dev/active/I-00079/evidences/pre/I-00079-queue-empty-state.png` — the empty Queue showing the "How to design an item →" CTA.
- `ai-dev/active/I-00079/evidences/pre/I-00079-broken-link-404.png` — the `{"detail":"Not Found"}` page after clicking the CTA (URL bar shows `http://localhost:9900/docs/IW_AI_Core_CLI_Spec.md`).
- `ai-dev/active/I-00079/evidences/pre/I-00079-queue-snapshot.yml` — accessibility snapshot of the empty Queue page (the `<a>` element shows `/url: /docs/IW_AI_Core_CLI_Spec.md`).

## Browser Verification Script (pre-fix reproduction)

```bash
playwright-cli kill-all
playwright-cli open "http://localhost:9900/project/cv/queue"
# snapshot shows: link "How to design an item →" → /url: /docs/IW_AI_Core_CLI_Spec.md
playwright-cli click <ref-of-the-CTA-link>
# page body is now: {"detail":"Not Found"}  (HTTP 404)
```

## Root Cause Analysis

The dashboard renders project docs through `dashboard/routers/system.py`:

- `system.py:40` — `router = APIRouter(prefix="/system")`
- `system.py:438` — `@router.get("/docs/{doc_path:path}", response_class=HTMLResponse)` — so docs live at **`/system/docs/<key>`**, where `<key>` is the path under `docs/` with the `.md` suffix **stripped** (`system.py:417-420` builds `_DOC_URL_MAP` via `_DOCS_DIR.rglob("*.md")`, key = `relative_to(_DOCS_DIR).with_suffix("").as_posix()`). CR-00044 additionally registers curated `**/CLAUDE.md` paths and supports subdirectory keys like `implementation/00_INDEX`.

`dashboard/routers/docs_global.py` registers only `GET /docs` (exact) and `GET /api/docs/search` — there is no `/docs/{path}` route — so `GET /docs/IW_AI_Core_CLI_Spec.md` falls through to FastAPI's default 404 (`{"detail":"Not Found"}`).

The empty-state panels are rendered by the `empty_state(...)` macro (`dashboard/templates/macros/empty_state.html:7`), which drops `primary_href` straight into `<a href="{{ primary_href }}">`. Six call sites pass the pre-`/system`, `.md`-suffixed form `/docs/<name>.md`.

**Why this slipped through:** CR-00042 ("Fix Broken 'Open full docs' Links in Help Popups") corrected the same class of broken link, but only in `dashboard/routers/help.py`'s `_SLUG_TO_DOC` map (the help-popover links) — it never touched the `empty_state` macro `primary_href` values in the page templates. CR-00044 refined those same help mappings and added subdir/`CLAUDE.md` doc serving + a favicon route — again without touching the empty-state CTAs. So the empty-state CTAs are residual instances of the exact bug CR-00042 set out to fix, just outside CR-00042's scope. The existing regression test `tests/dashboard/test_empty_states.py` asserts the empty-state *markup markers* (the `data-empty-state`, `<h3>`, `<p>`, `class="empty-state__cta-primary"` are present) but never follows or validates `primary_href`, so a broken target passes the suite (a classic "shape, not semantics" gap — the I003 lesson).

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/pages/project/queue.html` (×2 empty-state blocks) | "How to design an item →" CTA 404s |
| `dashboard/templates/pages/project/history.html` | "How execution works →" CTA 404s |
| `dashboard/templates/pages/project/batches.html` | "About batches →" CTA 404s |
| `dashboard/templates/pages/system/all_active.html` | "Daemon overview →" CTA 404s |
| `dashboard/templates/docs_library.html` | "Doc catalogue →" CTA 404s |
| `dashboard/templates/research_library.html` | "Open the catalogue →" CTA 404s |
| `tests/dashboard/test_empty_states.py` | Has no assertion that `primary_href` resolves — let a broken link ship |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | frontend-impl | Update the 7 `empty_state` `primary_href` values across the 6 templates to the `/system/docs/<key>` form | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | tests-impl | Reproduction + regression test: every empty-state page's `empty-state__cta-primary` href resolves to HTTP 200 (and contains no `.md` suffix / no bare `/docs/` prefix) | — |
| S04 | code-review-impl | Per-agent review of S03 | — |
| S05 | code-review-final-impl | Global cross-agent review of all I-00079 work | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `make format-check` | — |
| S08 | qv-gate | `make type-check` | — |
| S09 | qv-gate | `make test-unit` | — |
| S10 | qv-gate | `make test-integration` | — |
| S11 | qv-browser | Browser verification — empty-state CTAs resolve to the doc page, no console errors, no regressions | — |
| S12 | self-assess-impl | Self-assessment via `iw-item-analyze` (project has `self_assess = true`) | — |

Agent slugs: `frontend-impl`, `code-review-impl`, `code-review-final-impl`, `tests-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no schema changes.

### Code Changes

- **Files to modify**:
  - `dashboard/templates/pages/project/queue.html` — lines 97 & 197: `/docs/IW_AI_Core_CLI_Spec.md` → `/system/docs/IW_AI_Core_CLI_Spec#iw-approve`
  - `dashboard/templates/pages/project/history.html` — line 139: `/docs/IW_AI_Core_Architecture.md` → `/system/docs/IW_AI_Core_Architecture`
  - `dashboard/templates/pages/project/batches.html` — line 137: `/docs/IW_AI_Core_Daemon_Design.md#batches` → `/system/docs/IW_AI_Core_Daemon_Design#batches`
  - `dashboard/templates/pages/system/all_active.html` — line 72: `/docs/IW_AI_Core_Daemon_Design.md` → `/system/docs/IW_AI_Core_Daemon_Design`
  - `dashboard/templates/docs_library.html` — line 129: `/docs/implementation/00_INDEX.md` → `/system/docs/implementation/00_INDEX`
  - `dashboard/templates/research_library.html` — line 149: `/docs/implementation/00_INDEX.md` → `/system/docs/implementation/00_INDEX`
  - `tests/dashboard/test_empty_states.py` — add the resolves-to-200 assertion (S03)
- **Nature of change**: Correct broken doc URLs in template strings; add a regression test that follows each `primary_href`.
- **Targets chosen to match `help.py`'s `_SLUG_TO_DOC` map** (post-CR-00044), so the empty-state CTA and the help-popover "Open full docs" link for the same page point at the same doc. `implementation/00_INDEX` resolves because CR-00044 added subdirectory doc serving (`system.py:417-420` `rglob`); confirm it returns 200 in the regression test.

## File Manifest

All files for this work item live under `ai-dev/active/I-00079/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00079_Issue_Design.md` | Design | This document |
| `I-00079_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/I-00079_S01_frontend-impl_prompt.md` | Prompt | S01 fix instructions |
| `prompts/I-00079_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review of S01 |
| `prompts/I-00079_S03_tests-impl_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00079_S04_CodeReview_prompt.md` | Prompt | S04 per-agent review of S03 |
| `prompts/I-00079_S05_CodeReview_Final_prompt.md` | Prompt | S05 global cross-agent review |
| `prompts/I-00079_S11_BrowserVerification_prompt.md` | Prompt | S11 browser verification |
| `prompts/I-00079_S12_SelfAssess_prompt.md` | Prompt | S12 self-assessment |

Reports are created during execution in `ai-dev/active/I-00079/reports/`.

## Test to Reproduce

Write a failing test that demonstrates the bug before fixing it.

**Test-file location** — `tests/dashboard/test_empty_states.py` (extend it). It already uses the `client` fixture (registered only in `tests/dashboard/conftest.py`); a test placed under `tests/unit/` or `tests/integration/` fails with `fixture 'client' not found` (I-00067).

```python
import re

# Each (route_factory, slug) pair already rendered by an existing test in this file.
# For the project-scoped pages use the test_project fixture; for the global ones a
# plain client.get(path) works.

_EMPTY_STATE_PAGES = [
    # (path-builder, expected slug)
    (lambda p: f"/project/{p.id}/queue",   "queue"),
    (lambda p: f"/project/{p.id}/history", "history"),
    (lambda p: f"/project/{p.id}/batches", "batches"),
    # global pages (no project): handled separately below
]


def _primary_hrefs(html: str) -> list[str]:
    """Return every empty-state primary CTA href in the rendered HTML."""
    return re.findall(
        r'<a\s+href="([^"]+)"\s+class="empty-state__cta-primary"', html
    )


def test_i00079_queue_empty_state_cta_resolves(client, test_project) -> None:
    """The 'How to design an item →' CTA must NOT 404.

    Pre-fix: href == '/docs/IW_AI_Core_CLI_Spec.md' → GET returns 404.
    Post-fix: href == '/system/docs/IW_AI_Core_CLI_Spec#iw-approve' → GET returns 200.
    """
    resp = client.get(f"/project/{test_project.id}/queue")
    assert resp.status_code == 200
    hrefs = _primary_hrefs(resp.text)
    assert hrefs, "queue empty state must render a primary CTA"
    for href in hrefs:
        # semantic: the broken pattern must be gone
        assert not href.startswith("/docs/"), f"stale bare /docs/ link: {href}"
        assert ".md" not in href.split("#")[0], f"stale .md suffix in link: {href}"
        # semantic: the link must actually resolve
        target = href.split("#")[0]
        followed = client.get(target)
        assert followed.status_code == 200, (
            f"empty-state CTA {href!r} → {followed.status_code}"
        )
    # be explicit about the expected destination
    assert any(h.startswith("/system/docs/IW_AI_Core_CLI_Spec") for h in hrefs)
```

(Repeat the resolve-and-no-stale-pattern check for `history`, `batches`, the system `all-active` page, and the global `docs_library` / `research_library` pages — see the S03 prompt for the full list. Assert the *specific* expected destination for each, not merely "some 200".)

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a dashboard page with an empty list (Queue, History, Batches, All Active Work, Docs library, Research library)
When the user clicks the empty-state panel's primary call-to-action link
Then the browser opens the corresponding /system/docs/<DocName> page (HTTP 200), not a {"detail":"Not Found"} 404 page
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then a test in tests/dashboard/test_empty_states.py renders each empty-state page, extracts the empty-state__cta-primary href, asserts it does not start with "/docs/" and has no ".md" suffix, and asserts a GET on that href returns 200 — and this test fails against the pre-fix templates
```

### AC3: Empty-state CTA and help-popover link agree

```
Given a page that has both an empty-state CTA and a contextual help popover (Queue, History, Batches, All Active Work)
When you compare the empty-state CTA's primary_href with help.py's _SLUG_TO_DOC entry for that page's slug
Then both point at a real /system/docs/<DocName> document with no ".md" suffix and no bare "/docs/" prefix — the same document for Queue (/system/docs/IW_AI_Core_CLI_Spec#iw-approve, exact match), Batches (/system/docs/IW_AI_Core_Daemon_Design, the CTA adding an #batches anchor), and All Active Work (/system/docs/IW_AI_Core_Daemon_Design); History's CTA deliberately points at /system/docs/IW_AI_Core_Architecture (matching its "How execution works →" label) rather than help.py's /system/docs/IW_AI_Core_CLI_Spec — a documented divergence, not drift
```

## Regression Prevention

- The new test in `tests/dashboard/test_empty_states.py` follows every `empty-state__cta-primary` href and asserts a 200, so any future empty-state CTA pointing at a non-existent route fails CI — closing the "shape, not semantics" gap that let this bug ship.
- Targets are aligned with `help.py`'s `_SLUG_TO_DOC` map, so the two surfaces for the same page can't drift independently without a test noticing (AC3).

## Dependencies

- **Depends on**: None (CR-00044's subdirectory doc serving is already merged on `main`).
- **Blocks**: None.

## Impacted Paths

- `dashboard/templates/pages/project/queue.html`
- `dashboard/templates/pages/project/history.html`
- `dashboard/templates/pages/project/batches.html`
- `dashboard/templates/pages/system/all_active.html`
- `dashboard/templates/docs_library.html`
- `dashboard/templates/research_library.html`
- `tests/dashboard/test_empty_states.py`

## TDD Approach

- Reproducing test: `test_i00079_*_cta_resolves` in `tests/dashboard/test_empty_states.py` — fails against the pre-fix templates (GET on `/docs/<name>.md` → 404), passes after.
- Unit tests: n/a (template-only change; nothing to unit-test in isolation).
- Integration tests: the dashboard `client`-fixture tests above run under `make test-integration` via `tests/dashboard/`; no testcontainer DB needed.

**Assertion scoping for href checks** — match the attribute-scoped form `<a href="..." class="empty-state__cta-primary">` (the macro emits the `href` then the `class`, in that order — see `dashboard/templates/macros/empty_state.html:7`). Do not do a bare-substring search for `IW_AI_Core_CLI_Spec` in the page HTML — the same token can appear in a help-popover link too; key on the `empty-state__cta-primary` class.

## Notes

- Pure template + test change. No Python route changes, no DB, no migrations, no `make css` (Tailwind is prebuilt and unaffected by an href-string edit).
- `make lint` runs `scripts/check_templates.py` over the Jinja2 templates; an href-string change won't trip the `format`-filter rule, but run the gate anyway.
- Keep the fix minimal — only change the `primary_href` values and add the regression test. Do not refactor the `empty_state` macro or restyle the panels.
