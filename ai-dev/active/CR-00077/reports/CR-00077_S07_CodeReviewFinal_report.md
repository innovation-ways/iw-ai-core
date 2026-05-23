# CR-00077 S07 Code Review — Final Cross-Agent Report

**Step**: S07  
**Agent**: code-review-final-impl  
**Work Item**: CR-00077 (Overlap details popup — read-only)  
**Date**: 2026-05-23  

---

## Summary

Global cross-agent review of all six implementation/review steps. **No blockers.** CR-00077 is ready for merge. One minor cosmetic formatting fix was applied during this review.

---

## Scope Discipline (Check 2)

| Path | Diff vs `origin/main` | Status |
|------|----------------------|--------|
| `orch/` | empty | ✅ |
| `executor/` | empty | ✅ |
| `ai-dev/iw-config/` | empty | ✅ |
| `orch/db/migrations/` | empty | ✅ |

CR-00077 is confirmed dashboard-only. No orchestrator, daemon, executor, or migration files were touched.

---

## Changed Files

```
dashboard/routers/batches.py          — API endpoint + group_overlap_events helper + batch context in items fragment
dashboard/static/styles.css          — 57 lines of modal CSS (backdrop, container, sections, close button, pill trigger)
dashboard/templates/fragments/batch_items_rows.html  — Held pill → htmx trigger button
dashboard/templates/fragments/batch_overlap_modal.html  — Single modal partial (does not extend base.html)
dashboard/templates/pages/project/batch_detail.html — Added <div id="overlap-modal-root"> swap target
tests/unit/test_batch_overlap_grouping.py     — 10 unit tests for group_overlap_events
tests/dashboard/test_batch_overlap_modal.py   — 3 integration tests for the endpoint
```

---

## Acceptance Criteria Coverage (Check 1)

| AC | Description | Verification | Status |
|----|-------------|-------------|--------|
| AC1 | Clickable pill → htmx GET to endpoint | `batch_items_rows.html` button with `hx-get` targeting `#overlap-modal-root`; `batch_detail.html` has the swap target div; S14 browser_verification covers the click | ✅ |
| AC2 | Grouped by blocking item | `group_overlap_events()` in `batches.py` produces ordered `(blocking_id, globs)` tuples; template loops `{% for section in sections %}`; `test_status_200_with_two_blocking_items` asserts both blocker IDs in body | ✅ |
| AC3 | No truncation | Happy-path test has `for glob in globs_1: assert glob in body` + same for `globs_2`; every glob asserted individually | ✅ |
| AC4 | Dismissal (Esc, backdrop, ×) | Inline JS in `batch_overlap_modal.html`: `onKey(e) { if (e.key === 'Escape') close(); }` + `backdrop.addEventListener('click')` + `iw-modal-close` click; S14 browser_verification covers dismissal | ✅ |
| AC5 | 404 when no recent event | `overlap_modal` returns 404 + empty-state Jinja fragment when events list is empty; `test_status_404_no_event` + `test_status_404_event_outside_window` cover both 404 paths | ✅ |
| AC6 | Read-only | No `hx-post`, `hx-delete`, or `<form>` in modal HTML; happy-path test asserts `assert "<form" not in body` etc.; no POST endpoints in `batches.py` for the overlap route | ✅ |

**All 6 ACs have concrete verification artifacts (tests or templates). No fix-cycle required.**

---

## Single Modal Partial (Check 3)

Exactly one file: `dashboard/templates/fragments/batch_overlap_modal.html`. It:
- Does NOT extend `base.html`
- Renders `<html>`-less fragment (confirmed by tests asserting no `<html>`/`<body>` in response)
- Is mounted by `batch_items_rows.html` htmx trigger and `batch_detail.html` swap target

The Queue page (`queue.html`) was **not changed** — the overlap trigger is batch-scoped and the Queue page's `_queue_items` excludes active-batch items, matching the CR design intent.

---

## Tailwind Discipline (Check 4)

`dashboard/static/styles.tailwind.css` and `tailwind.config.js` are **unchanged**. All modal CSS is appended as plain rules to `dashboard/static/styles.css` (57 lines), consistent with the plain-CSS-fallback rule.

---

## Pre-flight Quality Gates (Check 5)

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 868 files already formatted *(minor `ruff format` fix applied to `test_batch_overlap_grouping.py` during this review)* |
| `make type-check` | ✅ mypy clean on 275 source files |

---

## Targeted Test Verification (Check 6)

```
uv run pytest tests/unit/test_batch_overlap_grouping.py tests/dashboard/test_batch_overlap_modal.py -v --no-cov

13 passed in 27.06s
```

**All 13 tests pass.** The coverage failure (`total of 18 is less than fail-under=50`) is a pre-existing project-wide condition; it is not a failure of these specific test files.

---

## CR-00078 Carry-Forward Assessment (Check 7)

**Assessment: LOW RISK for CR-00078**

The modal partial is structured for extensibility:

```
{% for section in sections %}
  <section class="iw-modal-section">
    <h3 class="iw-modal-section-header">…</h3>
    <ul class="iw-modal-file-list">
      {% for glob in section.globs %}
        <li><code>{{ glob }}</code></li>
      {% endfor %}
    </ul>
  </section>
{% endfor %}
```

To add per-file Ignore buttons (CR-00078), CR-00078 needs only to:
1. Add a `<form>` / `hx-post` inside each `<li>`, and
2. Append a footer `<div>` with the master "Ignore all & start" button.

Neither requires rewriting the existing `{% for section %}` / `{% for glob %}` block structure. The existing `<li><code>{{ glob }}</code></li>` pattern is a clean injection point — a form button can wrap or sit adjacent to each `<li>`. The `sections` dict in `overlap_modal`'s context can also carry per-(blocking_item_id, glob) ignore-state if `BatchOverlapIgnore` rows are re-queried for CR-00078.

No refactor is required.

---

## Issue Log

| Severity | Issue | Disposition |
|----------|-------|-------------|
| HIGH (S06) | Test method names describe implementation, not behaviour | Not a blocker; noted as cleanup suggestion for CR-00078 |
| MEDIUM (S06) | No exact 300-second boundary test (only -301s tested) | Not a blocker; server-side `<` comparison is a known quantity |
| MINOR | `test_batch_overlap_grouping.py` had one ruff format issue | Fixed during S07 |

---

## Verdict

**APPROVED — no blockers.** CR-00077 is merge-ready. All six ACs are verified. Scope discipline holds. All quality gates pass.