# I-00095: Auto-merge events table columns are not sortable

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-17
**Reported By**: sergio (manual UX audit of `/project/iw-ai-core/auto-merge`)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures exempt.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Description

The events table in `/project/<id>/auto-merge` has six columns
(timestamp, event_type, entity_id, message, verdict, actions) but the
column headers are static `<th>` text. Clicking a header does nothing.
The user expects clicking `timestamp` to sort ascending/descending,
`event_type` to group by type, `entity_id` to group by work item, etc.
Today the only ordering available is "created_at DESC fixed" coming
from `orch.auto_merge_aggregator.list_recent_events`.

## Project Context

Read `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`. The events
table fragment is at
`dashboard/templates/fragments/auto_merge_events_table.html`.

## Browser Evidence

- `ai-dev/active/I-00095/evidences/pre/I-00095-no-sort.png` — baseline
  events table; clicking any `<th>` does nothing (no styling change,
  no URL change, no fetch).

## Steps to Reproduce

1. Open `/project/iw-ai-core/auto-merge`.
2. Click any `<th>` text in the events table header (e.g.
   `timestamp`).

**Expected**: the table re-sorts and the clicked header indicates the
new sort direction (e.g. `timestamp ▼` for descending).

**Actual**: nothing happens — `<th>` are inert.

## Root Cause Analysis

`dashboard/templates/fragments/auto_merge_events_table.html:25-28`:

```jinja
<thead>
  <tr class="border-b border-border bg-muted/30 text-xs text-muted-foreground">
    <th class="px-3 py-2 text-left">timestamp</th>
    <th class="px-3 py-2 text-left">event_type</th>
    <th class="px-3 py-2 text-left">entity_id</th>
    <th class="px-3 py-2 text-left">message</th>
    <th class="px-3 py-2 text-left">verdict</th>
    <th class="px-3 py-2 text-left">actions</th>
  </tr>
</thead>
```

No click handlers, no URL building, no sort state. The aggregator at
`orch/auto_merge_aggregator.py:238-275` (`list_recent_events`) accepts
no sort parameter — it always orders by `DaemonEvent.created_at.desc()`.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/auto_merge_aggregator.py` (`list_recent_events`) | Add `sort` + `direction` params; map to safe `ORDER BY` |
| `dashboard/routers/auto_merge_ui.py` (`auto_merge_events`) | Accept `sort` and `dir` query params, validate, pass to aggregator |
| `dashboard/templates/fragments/auto_merge_events_table.html` | Headers become sortable controls (button/htmx); indicator chevron; preserves filter + page state |

## Fix Plan

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | Extend `list_recent_events(sort: str, direction: str)`; whitelist `sort` ∈ `{"created_at","event_type","entity_id","verdict"}` (message-text sort is low-value and expensive; skip it; actions has no sortable value). Whitelist `direction` ∈ `{"asc","desc"}`. Default behaviour unchanged (`created_at desc`). Add unit test for the new params. | — |
| S02 | `code-review-impl` | Review S01 | — |
| S03 | `api-impl` | Update `auto_merge_events` route signature: `sort: str | None`, `dir: str | None`, validate against the same whitelist, return 400 on invalid value, pass through. | — |
| S04 | `code-review-impl` | Review S03 | — |
| S05 | `frontend-impl` | Convert each sortable `<th>` into a `<button hx-get>` that toggles direction (asc ↔ desc) for the active column, switches to that column with `desc` if a different column is clicked. Append a small chevron (`↑`/`↓`) on the active column. Preserve current `type` filter and `page_size` in the URL. | — |
| S06 | `code-review-impl` | Review S05 | — |
| S07 | `tests-impl` | Unit: aggregator with each sort+direction combo. Dashboard: clicking a column header re-renders with sort param and chevron is in the right place. Reject test: `?sort=message` returns 400. | — |
| S08 | `code-review-impl` | Review S07 | — |
| S09 | `code-review-final-impl` | Global review | — |
| S10–S15 | `qv-gate` | lint, format, typecheck, security-sast, unit-tests, integration-tests | — |
| S16 | `qv-browser` | Playwright: click each sortable header; verify URL contains `sort=…&dir=…`; verify the indicator appears; verify direction toggles on the same column. | — |
| S17 | `self-assess-impl` | Self-assessment | — |

### Database Changes

None.

### Code Changes

- **Files to modify**:
  - `orch/auto_merge_aggregator.py`
  - `dashboard/routers/auto_merge_ui.py`
  - `dashboard/templates/fragments/auto_merge_events_table.html`
  - `dashboard/static/styles.css` (small chevron rule, optional)
- **Files to extend (tests)**:
  - `tests/unit/test_auto_merge_aggregator.py`
  - `tests/dashboard/test_auto_merge_routes.py`

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00095_Issue_Design.md` | Design | This document |
| `I-00095_Functional.md` | Design | Human summary |
| `workflow-manifest.json` | Manifest | Steps |
| `prompts/I-00095_S01_Backend_prompt.md` | Prompt | Aggregator sort params |
| `prompts/I-00095_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/I-00095_S03_Api_prompt.md` | Prompt | Route accepts sort/dir |
| `prompts/I-00095_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/I-00095_S05_Frontend_prompt.md` | Prompt | Sortable headers |
| `prompts/I-00095_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/I-00095_S07_Tests_prompt.md` | Prompt | Tests |
| `prompts/I-00095_S08_CodeReview_prompt.md` | Prompt | Review S07 |
| `prompts/I-00095_S09_CodeReview_Final_prompt.md` | Prompt | Final review |
| `prompts/I-00095_S16_BrowserVerification_prompt.md` | Prompt | Playwright |
| `prompts/I-00095_S17_SelfAssess_prompt.md` | Prompt | Self-assess |

## Test to Reproduce

```python
# Unit
def test_list_recent_events_sorts_by_event_type_asc(db_session, project_factory, daemon_event_factory):
    project = project_factory(...)
    for event_type in ("auto_merge_health_probe", "auto_merge_config_updated", "merge_auto_resolved"):
        daemon_event_factory(project_id=project.id, event_type=event_type, message="x")

    rows, total = list_recent_events(db_session, project.id, sort="event_type", direction="asc")
    types = [r.event_type for r in rows]
    assert types == sorted(types)


# Dashboard
def test_table_header_renders_clickable_sort_button_for_timestamp(client, project_factory):
    project = project_factory(...)
    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=10")
    html = response.text
    # The 'timestamp' header is a <button hx-get …> not static <th>text.
    import re
    assert re.search(r'<button\b[^>]*\bhx-get="[^"]*sort=created_at[^"]*"[^>]*>\s*timestamp', html)


def test_invalid_sort_param_returns_400(client, project_factory):
    project = project_factory(...)
    response = client.get(
        f"/project/{project.id}/auto-merge/events?page=0&page_size=10&sort=message"
    )
    assert response.status_code == 400
```

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge"
playwright-cli snapshot                   # find header refs
playwright-cli click <timestamp-header-ref>
playwright-cli screenshot                 # chevron should appear
playwright-cli click <timestamp-header-ref>   # toggle to asc
```

## Acceptance Criteria

### AC1: Sortable columns are clickable

```
Given the events table renders
Then headers timestamp, event_type, entity_id, verdict are <button hx-get …>
 AND each carries sort=<column>
```

### AC2: Sort indicator appears on the active column

```
Given the URL has ?sort=event_type&dir=asc
Then the event_type header carries a visible chevron (↑) and aria-sort="ascending"
 AND no other column carries a chevron
```

### AC3: Clicking toggles direction; clicking another column resets to desc

```
Given the URL is ?sort=created_at&dir=desc
When the user clicks the timestamp header
Then the URL becomes ?sort=created_at&dir=asc
When the user instead clicks event_type
Then the URL becomes ?sort=event_type&dir=desc (default starts desc)
```

### AC4: Invalid sort values are rejected

```
Given a request to /auto-merge/events with sort=message OR sort=actions OR dir=foo
When the server processes it
Then the response is HTTP 400
 AND the error message names the invalid parameter
```

### AC5: Filter + sort interoperate

```
Given the URL has ?type=merge_auto_resolved&sort=event_type
Then both the filter and the sort apply
 AND clicking pagination preserves both
```

### AC6: Regression tests exist

All named tests pass.

## Regression Prevention

- Whitelist-enum sort + direction params at the route + aggregator
  layers prevents SQL injection via raw column names.
- A test asserting `?sort=message → 400` keeps the whitelist locked
  down.

## Dependencies

- **Depends on**: None
- **Blocks**: None
- **Conflicts with**: I-00091, I-00092, I-00093, I-00094, I-00096, I-00097 (overlapping auto-merge fragments); run sequentially.

## Impacted Paths

- `orch/auto_merge_aggregator.py`
- `dashboard/routers/auto_merge_ui.py`
- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/static/styles.css`
- `tests/unit/test_auto_merge_aggregator.py`
- `tests/dashboard/test_auto_merge_routes.py`

## TDD Approach

- Reproducing tests:
  - `tests/unit/test_auto_merge_aggregator.py::test_list_recent_events_sorts_by_event_type_asc`
  - `tests/unit/test_auto_merge_aggregator.py::test_list_recent_events_rejects_unknown_sort_column`
  - `tests/dashboard/test_auto_merge_routes.py::test_table_header_renders_clickable_sort_button_for_timestamp`
  - `tests/dashboard/test_auto_merge_routes.py::test_invalid_sort_param_returns_400`
  - `tests/dashboard/test_auto_merge_routes.py::test_filter_and_sort_combine_correctly`
- Use attribute-scoped CSS class assertions (I-00067).

## Notes

- 5 of 7 audit incidents.
- "message" column is intentionally NOT sortable — sorting on a free-text
  field is rarely useful and slow at scale.
- "actions" column is non-data; not sortable.
- This is the largest of the six remaining audit incidents; if time is
  tight, ship it last.
