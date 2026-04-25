# I-00039: Jobs page — drop color-coded Type chips and replace filter checkboxes with multi-select dropdowns

**Type**: Issue
**Severity**: Low
**Created**: 2026-04-25
**Reported By**: sergio (via /iw-new-incident)
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

This incident has **NO database changes**. The migration policy is included for
agent-context completeness only.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Description

The Jobs page (`/project/{id}/jobs`) has two visual issues that hurt readability
without adding information:

1. The **Type** column renders each job type as a colored chip (blue / purple /
   orange / teal / emerald). With six job types each in a different colour the
   table is noisy; the colour adds no information beyond the text label.
2. The **Type** and **Status** filters on top of the table are flat checkbox
   groups. There are six job types and six status values — together that is
   twelve checkboxes laid out across the filter row, which looks crowded and
   does not scale as more job types are added.

Both are cosmetic — no data risk, no correctness impact. The user-visible
impact is purely visual: the page feels busy and unprofessional.

## Project Context

Read `CLAUDE.md` for architecture, conventions, and hard rules. Read
`dashboard/CLAUDE.md` for the dashboard stack (FastAPI + Jinja2 + htmx +
prebuilt Tailwind), the rule that **fragments must NOT extend `base.html`**,
and the requirement to run `make css` after editing templates so the prebuilt
CSS picks up new utility classes.

## Browser Evidence

The pre-fix state was captured against the live dashboard at
`http://localhost:9900/project/iw-ai-core/jobs`:

- `ai-dev/active/I-00039/evidences/pre/I-00039-jobs-before.png` — full-page
  screenshot showing the Type chips in five different colours and the long
  rows of checkboxes for Type and Status.
- `ai-dev/active/I-00039/evidences/pre/I-00039-jobs-before.snapshot.yml` —
  Playwright accessibility snapshot of the same page.

## Steps to Reproduce

1. Start the platform: `./ai-core.sh start`.
2. Open `http://localhost:9900/project/iw-ai-core/jobs` in a browser.
3. Inspect the filter bar above the table.
4. Inspect the Type column in the table body.

**Expected**:
- The Type column renders the type name as plain text in the same standard
  text colour used by the Title column (no coloured pill).
- The Type filter is a single dropdown labelled "Type" (or "Type (N selected)")
  that, when clicked, opens a panel of checkboxes for multi-select.
- The Status filter is a single dropdown using the same component as Type.

**Actual**:
- Each Type cell is a coloured pill: `code_mapping` blue, `doc_generation`
  purple, `batch_execution` orange, `research` teal, `oss_scan` emerald,
  `doc_indexing` neutral (the only one without a colour entry — itself a
  symptom that the colour scheme is incidental, not informative).
- The Type filter is six checkboxes laid out horizontally; the Status filter
  is six more checkboxes on the same row. The combined width crowds the date
  inputs and the Filter button.

## Browser Verification Script

Reproduce against any running dashboard. The QV browser step uses the
worktree-spawned isolated stack (`$IW_BROWSER_BASE_URL`) — never a hardcoded
URL.

```bash
playwright-cli kill-all
playwright-cli open http://localhost:9900/project/iw-ai-core/jobs
playwright-cli screenshot --full-page \
  --filename ai-dev/active/I-00039/evidences/pre/I-00039-jobs-before.png
playwright-cli close
```

## Root Cause Analysis

### Type column color-coding

`dashboard/templates/fragments/jobs_table.html:21-32` defines a `type_chip`
macro that maps job-type strings to Tailwind background+text colour utility
classes. The macro is invoked at line 81 (`<td class="px-4 py-2">{{
type_chip(row.job_type.value) }}</td>`). The same macro is also defined (dead)
in `dashboard/templates/pages/project/jobs.html:21-32` — the page-level copy is
unused because the fragment defines its own.

### Filter checkboxes

`dashboard/templates/pages/project/jobs.html:44-70` renders the Type and
Status filters as inline `<label><input type="checkbox" name="type|status"
...></label>` groups inside the GET form. The form already produces the
correct query-string shape (repeated `?type=...&type=...`), and the FastAPI
route (`dashboard/routers/jobs_ui.py:37,107` — `type: list[str] = Query(...)`)
already accepts that shape. **The query contract does not need to change** —
only the rendering of the form controls needs to change.

There is no JavaScript framework in this stack. The dashboard uses prebuilt
Tailwind + htmx + a small amount of vanilla JS (e.g. `dashboard/static/`). A
multi-select dropdown can be implemented as a Jinja macro plus a tiny
vanilla-JS open/close popover — no new dependencies.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/fragments/jobs_table.html` | Type cell renders coloured pill via `type_chip` — must render plain text instead. The dead duplicate at `pages/project/jobs.html:21-32` must be deleted. |
| `dashboard/templates/pages/project/jobs.html` | Type and Status filters are flat checkbox groups — must be replaced with a multi-select dropdown component for both. Date inputs and the Filter / Clear buttons stay as-is. |
| `dashboard/templates/components/multi_select.html` (new) | Reusable Jinja macro that renders the dropdown button + checkbox popover. |
| `dashboard/static/multi_select.js` (new, ~30 lines) | Vanilla JS to toggle the popover open/close, update the button label "(N selected)", and close on outside-click / Escape. |
| `dashboard/static/styles.css` | Tailwind-prebuilt CSS — regenerated by `make css` after the template edits so new utility classes are not purged. |

**No router or Python changes.** The FastAPI route at
`dashboard/routers/jobs_ui.py` already accepts repeated `?type=...` and
`?status=...` query params (`list[str] = Query(default=None)`). The form
submission contract is preserved.

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Fix the bug: remove `type_chip` (both copies); render plain-text Type cell; build `components/multi_select.html` macro + `static/multi_select.js`; replace Type and Status filter checkbox groups with the new component on the Jobs page; run `make css`. | — |
| S02 | CodeReview_Frontend | Review S01 — template correctness, macro reuse, JS quality, accessibility (ARIA, keyboard), CSS regenerated, no regressions. | — |
| S03 | Tests | Reproduction + regression tests: assert the Type cell contains the type name as plain text WITHOUT the old per-type colour utility classes (`bg-blue-100`, `bg-purple-100`, `bg-orange-100`, `bg-teal-100`, `bg-emerald-100`); assert the rendered filter form includes the new multi-select dropdown markup (`data-multi-select` button + hidden checkbox panel) and NOT the previous flat `<label><input type="checkbox" name="type">` rows; assert filtering by multiple types still works (HTTP 200, only matching rows present). | — |
| S04 | CodeReview_Tests | Review S03 — tests assert specific values (semantic), not just response shape. | — |
| S05 | CodeReview_Final | Global cross-layer review of S01–S04. | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `uv run ruff format --check .` | — |
| S08 | qv-gate | `make typecheck` | — |
| S09 | qv-gate | `make test-unit` | — |
| S10 | qv-browser | Browser verification of the fix in the worktree's isolated stack. | — |

QV gate selection rationale: this is a pure-frontend (Jinja/CSS/JS) change with
no Python logic touched. `frontend-tsc`, `make test-frontend`,
`make arch-check`, `make security-sast`, and `make test-integration` are
deliberately omitted — they would either not exist for this stack
(`frontend-tsc`, `test-frontend`) or add cost without coverage value
(`integration-tests` are slow and exercise no path this change touches).

Agent slugs: `frontend-impl`, `tests-impl`, `code-review-impl`,
`code-review-final-impl`, `qv-gate`, `qv-browser`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — this is a pure UI change.

### Code Changes

- **Files to modify**:
  - `dashboard/templates/pages/project/jobs.html` — delete dead `type_chip`
    macro (lines 21-32); replace Type filter (lines 44-56) and Status filter
    (lines 58-70) with calls to the new `multi_select` macro; include
    `<script src="/static/multi_select.js">` once on this page.
  - `dashboard/templates/fragments/jobs_table.html` — delete `type_chip` macro
    (lines 21-32); replace its call site (line 81) with plain text
    `<td class="px-4 py-2 text-foreground">{{ row.job_type.value }}</td>` (or
    equivalent — match the Title column's text colour utility).
  - `dashboard/static/styles.css` — regenerated by `make css`.
- **Files to create**:
  - `dashboard/templates/components/multi_select.html` — reusable macro.
  - `dashboard/static/multi_select.js` — popover open/close + label update.
- **Nature of change**: Visual-only template refactor + small reusable
  component. Query-string contract unchanged; FastAPI route untouched.

## File Manifest

All files for this work item live under `ai-dev/active/I-00039/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00039_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00039_S01_Frontend_prompt.md` | Prompt | S01 fix instructions |
| `prompts/I-00039_S02_CodeReview_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00039_S03_Tests_prompt.md` | Prompt | S03 tests instructions |
| `prompts/I-00039_S04_CodeReview_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00039_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00039_S10_BrowserVerification_prompt.md` | Prompt | S10 browser verification |
| `evidences/pre/I-00039-jobs-before.png` | Evidence | Pre-fix screenshot (captured) |
| `evidences/pre/I-00039-jobs-before.snapshot.yml` | Evidence | Pre-fix Playwright snapshot |

Reports are created during execution under `ai-dev/active/I-00039/reports/`.

## Test to Reproduce

The reproduction test lives under `tests/dashboard/test_jobs_filter_ui.py`
(new file). It uses FastAPI's `TestClient` against a PostgreSQL testcontainer
(via the existing `tests/dashboard/conftest.py` fixtures — never the live DB).

```python
"""I-00039 reproduction + regression tests for the Jobs page filter UI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# Per-type background classes that should NO LONGER appear on the Type cell.
LEGACY_TYPE_COLOR_CLASSES = (
    "bg-blue-100",
    "bg-purple-100",
    "bg-orange-100",
    "bg-teal-100",
    "bg-emerald-100",
)


def test_jobs_type_cell_is_plain_text_no_color_chip(
    client: TestClient, test_project
) -> None:
    """RED before fix: the Type cell uses bg-* utility classes from type_chip.

    Asserts the FIX is in place: the rendered HTML must NOT contain any of the
    legacy per-type background classes anywhere on the Jobs page.
    """
    resp = client.get(f"/project/{test_project.id}/jobs")
    assert resp.status_code == 200
    html = resp.text
    for cls in LEGACY_TYPE_COLOR_CLASSES:
        assert cls not in html, (
            f"Legacy color class {cls!r} still present in Jobs page HTML — "
            "Type chip color-coding was not removed."
        )


def test_jobs_filter_uses_multiselect_dropdown_not_checkbox_groups(
    client: TestClient, test_project
) -> None:
    """RED before fix: Type/Status filters are inline <input type=checkbox name=type>.

    Asserts the FIX: the page renders a multi_select dropdown component
    (button + popover) for both filters, instead of flat checkbox rows.
    """
    resp = client.get(f"/project/{test_project.id}/jobs")
    assert resp.status_code == 200
    html = resp.text
    # The new component must be present for both filters.
    assert 'data-multi-select="type"' in html
    assert 'data-multi-select="status"' in html
    # The pre-fix flat-checkbox shape must NOT appear in the filter form.
    # (Checkboxes still exist INSIDE the dropdown panel, but they should be
    # wrapped by the data-multi-select container.)
    assert '<input type="checkbox" name="type"' not in html.replace(" ", "")
    assert '<input type="checkbox" name="status"' not in html.replace(" ", "")


def test_jobs_multi_value_type_filter_still_filters(
    client: TestClient, db_session, test_project
) -> None:
    """REGRESSION: query-string contract preserved.

    Submitting ?type=code_mapping&type=research must filter to those two types
    only (matches the pre-fix behaviour — the form must still emit repeated
    name=value pairs).
    """
    # Reuse the existing _seed_all_sources helper from tests/integration/test_jobs_api.py
    # or seed inline. See that test module for fixture patterns.
    # ... assertions follow the pattern in test_jobs_api.py:
    #     assert ids["cij_id"] in html        # code_mapping kept
    #     assert ids["res_doc_id"] in html    # research kept
    #     assert ids["batch_id"] not in html  # batch_execution excluded
    #     assert ids["dgj_id"] not in html    # doc_generation excluded
    raise NotImplementedError("Implement using the seed helper — see prompt S03")
```

The Tests step (S03) will replace the `NotImplementedError` body with a
working seed and finalise the assertions, following the pattern already
established by `tests/integration/test_jobs_api.py`.

## Browser Verification Test

The QV Browser step (S10) verifies the fix end-to-end against the
worktree-spawned isolated stack. See
`prompts/I-00039_S10_BrowserVerification_prompt.md` for the V1..V4 steps:

- **V1**: Type column renders as plain text (no coloured pills, no `bg-*`
  utility classes on Type cells).
- **V2**: Clicking the Type filter button opens a dropdown panel of
  checkboxes; selecting two and submitting produces a URL with
  `?type=A&type=B`, the table is filtered to those two types, and the button
  label updates to "Type (2 selected)".
- **V3**: Same flow on the Status filter.
- **V4** (No regressions): Clear filters and confirm the full table returns;
  Filter / Clear / date inputs still work; no new console errors.

## Acceptance Criteria

### AC1: Bug is fixed — Type column is plain text

```
Given a user opens /project/{id}/jobs
When the Jobs table renders rows for code_mapping, doc_generation, batch_execution, research, oss_scan, and doc_indexing job types
Then every Type cell shows the type name in the same standard text colour as the Title column
And no Type cell has a coloured background pill (no bg-blue-100, bg-purple-100, bg-orange-100, bg-teal-100, bg-emerald-100, or rounded-sm chip wrapper)
```

### AC2: Bug is fixed — Type and Status filters are multi-select dropdowns

```
Given a user opens /project/{id}/jobs
When they look at the filter bar above the table
Then the Type filter is a single button labelled "Type" (or "Type (N selected)" when N>0 are checked)
And the Status filter is a single button using the same component
And clicking either button opens a popover panel with checkboxes for each option
And the popover closes on outside-click and on Escape
And submitting the form produces repeated query parameters (?type=A&type=B&status=X) — same wire format as before
```

### AC3: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/dashboard/test_jobs_filter_ui.py passes
And the existing tests/integration/test_jobs_api.py tests still pass (filter behaviour unchanged)
```

### AC4: No regressions on adjacent flows

```
Given the fix is applied
When the user uses the Filter button, the Clear link, the From / To date inputs, the table sort headers, the row links, and the pagination controls
Then every adjacent control still works exactly as before
And no new console errors appear on the Jobs page
```

## Regression Prevention

- The Tests step (S03) asserts on **specific colour utility classes** by name
  (`bg-blue-100`, etc.) — if a future change re-introduces per-type colour
  pills, the test fails immediately rather than silently passing on shape.
- The dropdown component is implemented as a **reusable Jinja macro**
  (`dashboard/templates/components/multi_select.html`) — future filter bars
  can adopt the same component without copy-pasting the JS.
- The router contract is **explicitly unchanged**, so any future refactor of
  the form controls will fail the existing
  `tests/integration/test_jobs_api.py` tests if it breaks the
  `?type=...&type=...` wire format.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing test**: `tests/dashboard/test_jobs_filter_ui.py` —
  asserts the FIX is in place. Before the fix lands, this test FAILS because
  the Jobs page contains the legacy `bg-blue-100` / `bg-purple-100` / etc.
  utility classes from `type_chip` and contains the flat
  `<input type="checkbox" name="type">` rows. After the fix, both assertions
  pass.
- **Unit tests**: None required — there is no Python logic to unit-test
  (router untouched, no new service code).
- **Integration tests**: The new tests in `tests/dashboard/` exercise the full
  HTTP round-trip via `TestClient` against a PostgreSQL testcontainer (see
  `tests/dashboard/conftest.py`), which is the project's standard pattern for
  template-rendering tests.
- **Browser tests**: S10 (`qv-browser`) exercises the actual rendered page in
  Chromium against the worktree-spawned isolated stack.

## Notes

- The dashboard is **server-rendered Jinja2 + htmx + Tailwind (prebuilt) +
  small vanilla JS**. No React, no JS framework. Keep the multi-select
  implementation tiny: ~30 lines of vanilla JS, no dependencies.
- After editing templates that introduce new Tailwind utility classes, run
  `make css` so the prebuilt `dashboard/static/styles.css` is regenerated and
  committed alongside the template edits — see `dashboard/CLAUDE.md`.
- Accessibility: the dropdown button needs `aria-haspopup="listbox"` (or
  similar), the popover needs to be keyboard-navigable, and pressing Escape
  must close it and return focus to the button.
- The legacy `type_chip` macro is duplicated in **two** files
  (`pages/project/jobs.html:21-32` AND `fragments/jobs_table.html:21-32`).
  Only the fragment copy is invoked. Delete BOTH copies as part of S01.
- This incident does NOT change the FastAPI route handlers in
  `dashboard/routers/jobs_ui.py`. If S01 finds itself editing Python files
  outside the `dashboard/templates/` and `dashboard/static/` trees, that is a
  scope creep — STOP and raise a blocker.
