# I-00096: Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-17
**Reported By**: sergio (manual UX audit of `/project/iw-ai-core/auto-merge`)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Description

Two related defects on the same view:

1. **Status chip is rendered twice**: the same chip ("P1 opencode/.../
   …. ● down") appears in BOTH the global topbar and inside the page
   header on `/project/<id>/auto-merge`. Both link to the auto-merge
   page itself, so the in-page chip is doubly useless.
2. **The "all" filter shows every daemon event for the project**, not
   just auto-merge events. The page dumps `step_launched`,
   `step_completed`, `item_approved`, `step_crashed`, `fix_cycle_*`
   alongside actual auto-merge events. On a busy project these
   outnumber the auto-merge events 5-to-1, drowning out the signal
   the page is named for.

## Project Context

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`. Relevant
existing code: `dashboard/templates/pages/project/auto_merge.html`
(which includes `auto_merge_status_chip.html` once), plus whatever
base template renders the topbar chip (likely `dashboard/templates/base.html`
or a partials file).

## Browser Evidence

- `ai-dev/active/I-00096/evidences/pre/I-00096-chip-duplication.png` —
  full page screenshot showing the same chip at the top-right of the
  topbar AND inside the "Auto-Merge Resolver" page header. Also shows
  rows of `step_launched`/`step_completed` events that aren't auto-merge.

## Steps to Reproduce

1. Open `/project/iw-ai-core/auto-merge`.

**Expected**:
- Exactly one status chip on the page.
- The events table's default view shows only auto-merge events.

**Actual**:
- Two chips with identical content, both linking back to the same
  page.
- The table shows the project's full daemon-event feed by default.

## Root Cause Analysis

### Defect A — duplicated chip

`dashboard/templates/pages/project/auto_merge.html:13` includes the
chip:

```jinja
{% include "fragments/auto_merge_status_chip.html" %}
```

And the dashboard's global topbar (rendered by the project layout —
likely `dashboard/templates/components/topbar.html` or
`base.html` itself) ALSO renders an auto-merge chip via a context
flag. The chip endpoint `/auto-merge/status?compact=true` is
designed for the topbar (see `auto_merge_status.py` route's
`compact` branch at lines 115-135). The page-level template then
renders the rich version. Result: both render.

The fix is to suppress one of them on the auto-merge page itself —
typically the topbar chip becomes useless on the page it links to.

### Defect B — non-auto-merge events shown by default

`orch/auto_merge_aggregator.py:238-275` (`list_recent_events`) queries
ALL `DaemonEvent` rows for the project; `event_type_filter` is only
applied if non-None. The "all" filter (the default) passes
`type=None` → no event_type filter → every daemon event for the
project.

The page is named "Auto-Merge Resolver"; the "all" filter should
mean "all auto-merge events" — i.e., events whose `event_type`
starts with `merge_auto_` or `auto_merge_`. A "Show all daemon events"
toggle can be added for power users.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/base.html` or topbar partial | Renders the duplicate chip; needs a `{% if not on_auto_merge_page %}` guard |
| `dashboard/routers/auto_merge_ui.py` (`auto_merge_page` or `auto_merge_status`) | Communicates "we are on the auto-merge page" to the chip include — already set via `request.state.auto_merge_status_for_chip` |
| `orch/auto_merge_aggregator.py` (`list_recent_events`) | Apply auto-merge prefix filter on `type=None` |
| `dashboard/templates/fragments/auto_merge_events_table.html` | Add a toggle "Show all daemon events" chip that explicitly opts out of the prefix filter |

## Fix Plan

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `frontend-impl` | (a) Locate the topbar chip render path; suppress it on `/project/<id>/auto-merge` (use the existing `request.state.auto_merge_status_for_chip` flag or add a `is_auto_merge_page` flag). (b) Add a "Show all daemon events" toggle to `auto_merge_events_table.html` filter row. | — |
| S02 | `code-review-impl` | Review S01 | — |
| S03 | `backend-impl` | In `list_recent_events`, default to filtering `event_type` LIKE `merge_auto_%` OR LIKE `auto_merge_%` when `event_type_filter is None`. Add a new parameter `include_non_auto_merge: bool = False` that bypasses the prefix filter (used by the "Show all" toggle). | — |
| S04 | `code-review-impl` | Review S03 | — |
| S05 | `api-impl` | Route accepts `?all=1` (or equivalent) param and passes `include_non_auto_merge=True` to the aggregator. | — |
| S06 | `code-review-impl` | Review S05 | — |
| S07 | `tests-impl` | Unit: aggregator default filters by prefix, `include_non_auto_merge=True` bypasses. Dashboard: page renders only one chip (no `auto-merge-chip--compact` AND no in-page chip rendered together). Dashboard: default `/auto-merge/events` excludes `step_launched`. Dashboard: `?all=1` includes everything. | — |
| S08 | `code-review-impl` | Review S07 | — |
| S09 | `code-review-final-impl` | Global review | — |
| S10–S15 | `qv-gate` | lint, format, typecheck, security-sast, unit-tests, integration-tests | — |
| S16 | `qv-browser` | Playwright: exactly one chip; default view shows only auto-merge events; "Show all" toggle includes everything. | — |
| S17 | `self-assess-impl` | Self-assessment | — |

### Database Changes

None.

### Code Changes

- **Files to modify**:
  - `dashboard/templates/base.html` (or the topbar partial — locate via grep)
  - `dashboard/templates/fragments/auto_merge_events_table.html`
  - `dashboard/routers/auto_merge_ui.py`
  - `orch/auto_merge_aggregator.py`
- **Files to extend (tests)**:
  - `tests/unit/test_auto_merge_aggregator.py`
  - `tests/dashboard/test_auto_merge_routes.py`

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00096_Issue_Design.md` | Design | This document |
| `I-00096_Functional.md` | Design | Human summary |
| `workflow-manifest.json` | Manifest | Steps |
| `prompts/I-00096_S01_Frontend_prompt.md` | Prompt | Chip dedup + toggle UI |
| `prompts/I-00096_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/I-00096_S03_Backend_prompt.md` | Prompt | Aggregator prefix filter |
| `prompts/I-00096_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/I-00096_S05_Api_prompt.md` | Prompt | Route param |
| `prompts/I-00096_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/I-00096_S07_Tests_prompt.md` | Prompt | Tests |
| `prompts/I-00096_S08_CodeReview_prompt.md` | Prompt | Review S07 |
| `prompts/I-00096_S09_CodeReview_Final_prompt.md` | Prompt | Final review |
| `prompts/I-00096_S16_BrowserVerification_prompt.md` | Prompt | Playwright |
| `prompts/I-00096_S17_SelfAssess_prompt.md` | Prompt | Self-assess |

## Test to Reproduce

```python
# Unit
def test_list_recent_events_default_excludes_non_auto_merge(db_session, project_factory, daemon_event_factory):
    project = project_factory(...)
    daemon_event_factory(project_id=project.id, event_type="step_launched", message="x")
    daemon_event_factory(project_id=project.id, event_type="auto_merge_health_probe", message="probe")
    rows, _ = list_recent_events(db_session, project.id)
    types = {r.event_type for r in rows}
    assert "step_launched" not in types, "default view must hide non-auto-merge events"
    assert "auto_merge_health_probe" in types


def test_list_recent_events_include_non_auto_merge_shows_everything(db_session, project_factory, daemon_event_factory):
    project = project_factory(...)
    daemon_event_factory(project_id=project.id, event_type="step_launched", message="x")
    daemon_event_factory(project_id=project.id, event_type="auto_merge_health_probe", message="probe")
    rows, _ = list_recent_events(db_session, project.id, include_non_auto_merge=True)
    types = {r.event_type for r in rows}
    assert "step_launched" in types
    assert "auto_merge_health_probe" in types


# Dashboard
def test_auto_merge_page_renders_exactly_one_chip(client, project_factory):
    project = project_factory(...)
    response = client.get(f"/project/{project.id}/auto-merge")
    html = response.text
    # The chip's distinguishing element is its id="auto-merge-status-chip"
    assert html.count('id="auto-merge-status-chip"') == 1
```

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge"
playwright-cli snapshot                       # count chip refs (should be 1)
```

## Acceptance Criteria

### AC1: Exactly one status chip on the auto-merge page

```
Given the user is on /project/<id>/auto-merge
Then the rendered HTML contains exactly one element with id="auto-merge-status-chip"
```

### AC2: Other pages still show the compact topbar chip

```
Given the user is on /project/<id>/queue (or any non-auto-merge page)
And the project's auto-merge phase >= 1
Then the topbar shows the compact auto-merge chip
```

### AC3: Default events view excludes non-auto-merge events

```
Given the user GETs /project/<id>/auto-merge/events with no filter
Then the response does NOT include events with event_type 'step_launched', 'step_completed', 'item_approved', 'fix_cycle_started', 'fix_cycle_completed', 'step_crashed'
 AND it DOES include events with event_type matching merge_auto_* or auto_merge_*
```

### AC4: "Show all daemon events" toggle works

```
Given the user clicks the "Show all daemon events" toggle (or visits /auto-merge/events?all=1)
Then the response includes both auto-merge and non-auto-merge events
```

### AC5: Regression tests exist

All named tests pass.

## Regression Prevention

- The `event_type LIKE 'auto_merge_%' OR LIKE 'merge_auto_%'` rule is
  expressed in one place (`list_recent_events`); adding a new
  auto-merge event_type that follows the prefix convention
  automatically shows up.
- A test asserts the auto-merge page renders exactly one chip.

## Dependencies

- **Depends on**: None
- **Blocks**: None
- **Conflicts with**: I-00091, I-00092, I-00093, I-00094, I-00095, I-00097 (overlapping auto-merge fragments + same aggregator function); run sequentially.

## Impacted Paths

- `dashboard/templates/base.html`
- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/routers/auto_merge_ui.py`
- `orch/auto_merge_aggregator.py`
- `tests/unit/test_auto_merge_aggregator.py`
- `tests/dashboard/test_auto_merge_routes.py`

## TDD Approach

- Reproducing tests:
  - `tests/unit/test_auto_merge_aggregator.py::test_list_recent_events_default_excludes_non_auto_merge`
  - `tests/unit/test_auto_merge_aggregator.py::test_list_recent_events_include_non_auto_merge_shows_everything`
  - `tests/dashboard/test_auto_merge_routes.py::test_auto_merge_page_renders_exactly_one_chip`
  - `tests/dashboard/test_auto_merge_routes.py::test_topbar_chip_appears_on_non_auto_merge_page`
  - `tests/dashboard/test_auto_merge_routes.py::test_show_all_toggle_includes_non_auto_merge_events`

## Notes

- 6 of 7 audit incidents.
- The prefix list could be extracted to a module-level constant
  (`AUTO_MERGE_EVENT_PREFIXES = ("auto_merge_", "merge_auto_")`) for
  reuse and explicit auditability.
