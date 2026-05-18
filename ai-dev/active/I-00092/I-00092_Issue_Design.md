# I-00092: Auto-merge filter chip never highlights the active filter

**Type**: Issue
**Severity**: High
**Created**: 2026-05-17
**Reported By**: sergio (manual UX audit of `/project/iw-ai-core/auto-merge`)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item.

## Description

In the Auto-Merge events table at `/project/<id>/auto-merge`, the filter
chip row (`all`, `resolved`, `attempted`, `failed`, `skipped`,
`health_probe`, `config_updated`) never highlights the currently-active
filter. Clicking `resolved` correctly filters the table to
`merge_auto_resolved` events but no chip lights up — every chip stays
in the unselected style. The user cannot tell which filter they applied.

## Project Context

Read the project's `CLAUDE.md`. Relevant sub-CLAUDE: `dashboard/CLAUDE.md`
(htmx + Jinja2 fragment patterns).

## Browser Evidence

- `ai-dev/active/I-00092/evidences/pre/I-00092-filter-no-highlight.png`
  — after clicking the "resolved" filter, the URL is
  `…/auto-merge/events?type=merge_auto_resolved` and the table is empty
  (correctly filtered), but no chip in the row is highlighted.

## Steps to Reproduce

1. `GET /project/iw-ai-core/auto-merge`.
2. Click the `resolved` filter chip in the events section.

**Expected**: the `resolved` chip is highlighted (`bg-primary`,
`text-primary-foreground`, `border-primary`). The `all` chip is no
longer highlighted.

**Actual**: ALL chips remain in the default `border-border
text-muted-foreground` style. Filtering works (the events table content
changes) but the user has no visual indication of which filter is
active.

## Root Cause Analysis

`dashboard/templates/fragments/auto_merge_events_table.html:1-21`:

```jinja
{% set type_filter = request.query_params.get('type', 'all') %}
{% set filters = [
  ('all', 'all', None),
  ('resolved', 'resolved', 'merge_auto_resolved'),
  ('attempted', 'attempted', 'merge_auto_resolution_attempted'),
  ('failed', 'failed', 'merge_auto_resolution_failed'),
  ('skipped', 'skipped', 'merge_auto_resolution_skipped'),
  ('health_probe', 'health_probe', 'auto_merge_health_probe'),
  ('config_updated', 'config_updated', 'auto_merge_config_updated')
] %}

<div class="space-y-3">
  <div class="flex flex-wrap gap-2">
    {% for key, label, mapped in filters %}
      {% set href = '/project/' ~ request.path_params.project_id ~ '/auto-merge/events?page=0&page_size=' ~ page_size ~ ('' if mapped is none else '&type=' ~ mapped) %}
      <a hx-get="{{ href }}" hx-target="#auto-merge-events" hx-swap="innerHTML"
         class="px-2 py-1 rounded border text-xs {% if type_filter == key or (key == 'all' and not request.query_params.get('type')) %}bg-primary text-primary-foreground border-primary{% else %}border-border text-muted-foreground{% endif %}">
        {{ label }}
      </a>
    {% endfor %}
  </div>
```

The filter URL is `…&type=merge_auto_resolved` so the query param
`type_filter == 'merge_auto_resolved'`. But the `key` used in the
`{% if type_filter == key %}` check is the short name `'resolved'`. The
comparison `'merge_auto_resolved' == 'resolved'` is permanently False
for every chip, so the active-chip branch never fires.

Confirmed via:
```
curl -s '…/auto-merge/events?type=merge_auto_resolved' | grep "bg-primary"
# (no output — no chip carries the active class)
```

A secondary issue: the chip labels (`resolved`, `attempted`, `failed`,
`skipped`) don't directly correspond to the underlying `event_type`
values (`merge_auto_resolved`, …). A user reading the events table
column 2 can't easily map a label to its filter — adding `title="<full
event_type>"` tooltips improves discoverability.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/fragments/auto_merge_events_table.html` | Active-chip CSS never applied; label-to-event_type mapping is opaque |

## Fix Plan

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `frontend-impl` | Fix the comparison: compare `type_filter` to `mapped` (the actual URL value) instead of `key`. Add `title="{{ mapped or 'all event types' }}"` on each chip for discoverability. Apply ARIA: `aria-pressed="true"` on the active chip. | — |
| S02 | `code-review-impl` | Review S01 | — |
| S03 | `tests-impl` | Dashboard test: GET `/auto-merge/events?type=merge_auto_resolved` returns HTML where the `resolved` chip carries `bg-primary` AND no other chip carries it. Cover the `all` (no type param) case too. | — |
| S04 | `code-review-impl` | Review S03 | — |
| S05 | `code-review-final-impl` | Global review | — |
| S06–S11 | `qv-gate` | lint, format, typecheck, security-sast, unit-tests, integration-tests | — |
| S12 | `qv-browser` | Playwright: click each chip in turn; verify exactly one chip carries the active style; verify chip tooltip text matches the event_type column | — |
| S13 | `self-assess-impl` | Self-assessment | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migrations.

### Code Changes

- **Files to modify**:
  - `dashboard/templates/fragments/auto_merge_events_table.html` (the one-line comparison fix + title + aria attrs)
- **Files to create / extend (tests)**:
  - `tests/dashboard/test_auto_merge_routes.py` (extend)

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00092_Issue_Design.md` | Design | This document |
| `I-00092_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00092_S01_Frontend_prompt.md` | Prompt | Filter chip fix |
| `prompts/I-00092_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/I-00092_S03_Tests_prompt.md` | Prompt | Regression tests |
| `prompts/I-00092_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/I-00092_S05_CodeReview_Final_prompt.md` | Prompt | Global review |
| `prompts/I-00092_S12_BrowserVerification_prompt.md` | Prompt | Playwright verify |
| `prompts/I-00092_S13_SelfAssess_prompt.md` | Prompt | Self-assess |

## Test to Reproduce

```python
# tests/dashboard/test_auto_merge_routes.py — add

def test_filter_chip_resolved_is_highlighted_when_active(client, project_factory):
    project = project_factory(...)
    response = client.get(
        f"/project/{project.id}/auto-merge/events"
        "?page=0&page_size=10&type=merge_auto_resolved"
    )
    assert response.status_code == 200
    html = response.text

    chip_blocks = _extract_filter_chip_blocks(html)
    assert chip_blocks["resolved"].count("bg-primary") == 1, (
        f"'resolved' chip should carry bg-primary; got:\n{chip_blocks['resolved']}"
    )
    for key in ("all", "attempted", "failed", "skipped", "health_probe", "config_updated"):
        assert "bg-primary" not in chip_blocks[key], (
            f"'{key}' chip should NOT be highlighted when 'resolved' is active"
        )
```

Where `_extract_filter_chip_blocks` is a helper that returns the
rendered `<a>` for each chip keyed by its label.

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge"
playwright-cli snapshot                       # find filter chip refs
playwright-cli click <resolved-chip-ref>      # apply filter
playwright-cli screenshot                     # verify resolved is highlighted
```

## Acceptance Criteria

### AC1: Selected filter chip is highlighted

```
Given the user is on /project/<id>/auto-merge
When the user clicks the "resolved" chip
Then the "resolved" chip's outer <a> contains the bg-primary class
 AND no other chip's outer <a> contains bg-primary
```

### AC2: "all" chip is active when no type filter is in the URL

```
Given the user GETs /auto-merge/events with no `type` param
Then the "all" chip is highlighted and all other chips are not
```

### AC3: Each chip has a tooltip naming the full event_type

```
Given the rendered events table fragment
Then each chip's <a> element carries title="<full event_type or 'all event types'>"
 AND the active chip carries aria-pressed="true"; others carry aria-pressed="false"
```

### AC4: Regression test exists

```
Given the fix is applied
When the test suite runs
Then test_filter_chip_resolved_is_highlighted_when_active passes
 AND the parallel test for the "all" no-filter case passes
```

## Regression Prevention

- The fix moves comparison to the value the URL actually carries —
  changes to the chip label set cannot reintroduce the off-by-name
  mismatch.
- A regression test for each chip's active state would explode the
  matrix; instead, we test two representative cells (`resolved` active
  and `all` active when no `type` param), which collectively exercise
  the comparison branch.

## Dependencies

- **Depends on**: None
- **Blocks**: None
- **Conflicts with**: I-00091, I-00093, I-00094, I-00095, I-00096,
  I-00097 — all touch overlapping auto-merge fragments. The cross-batch
  launch-time gate will refuse to run any two of these in the same
  batch. Schedule them sequentially.

## Impacted Paths

- `dashboard/templates/fragments/auto_merge_events_table.html`
- `tests/dashboard/test_auto_merge_routes.py`

## TDD Approach

- Reproducing test: `tests/dashboard/test_auto_merge_routes.py::test_filter_chip_resolved_is_highlighted_when_active`
- Companion test: `test_filter_chip_all_is_highlighted_when_no_type_param`
- Use the attribute-scoped form for CSS class assertions (I-00067):
  `re.search(r'class\s*=\s*"[^"]*bg-primary[^"]*"', chip_block)`.

## Notes

- 2 of 7 audit incidents. Filed alongside I-00091, I-00093..I-00097.
- The fix is essentially a one-line template change plus accessibility
  polish; the bulk of the work is regression tests and verification.
