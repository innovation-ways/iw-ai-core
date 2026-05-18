# I-00093: Auto-merge event detail modal hides the most useful fields

**Type**: Issue
**Severity**: High
**Created**: 2026-05-17
**Reported By**: sergio (manual UX audit of `/project/iw-ai-core/auto-merge`)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item.

## Description

Clicking `(view)` on an auto-merge event in the table opens a modal
that shows only four fields: timestamp, type, entity_id, project_id.
It hides everything that makes the event diagnostically useful — the
event's `message` string, its full `event_metadata` JSON payload, its
`entity_type`, and (where applicable) its verdict info. For
`auto_merge_config_updated` events the metadata contains `old`/`new`
config + operator; for `auto_merge_health_probe` events it contains
`runtime_reachable`, `model`, `cli_tool`, latency; for resolved events
it contains `llm_calls` and refuse reasons. The user opens the modal
expecting these and sees a near-blank dialog.

Additionally the modal heading reads `Event #77992` — an opaque
internal id — instead of a human-readable label.

## Project Context

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`. Relevant
existing code: `dashboard/routers/auto_merge_ui.py:auto_merge_event_detail`
already loads the full event with metadata; only the template hides
most of it.

## Browser Evidence

- `ai-dev/active/I-00093/evidences/pre/I-00093-modal-incomplete.png` —
  modal for a health probe event showing only timestamp / type /
  entity_id (`—`) / project_id.

## Steps to Reproduce

1. `GET /project/iw-ai-core/auto-merge`.
2. Click `(view)` on any event row (works for every event type).

**Expected**: The modal shows the event's message, full metadata, and
contextual labels.

**Actual**: Four fields only; the metadata JSON is silently dropped
and the heading is `Event #<id>`.

## Root Cause Analysis

`dashboard/templates/fragments/auto_merge_event_detail.html:20-30`:

```jinja
<dl class="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
  <div><dt class="text-muted-foreground">timestamp</dt><dd>{{ event.created_at | localdt('%Y-%m-%d %H:%M:%S') }}</dd></div>
  <div><dt class="text-muted-foreground">type</dt><dd>{{ event.event_type }}</dd></div>
  <div><dt class="text-muted-foreground">entity_id</dt><dd class="font-mono">{{ event.entity_id or '—' }}</dd></div>
  <div><dt class="text-muted-foreground">project_id</dt><dd class="font-mono">{{ event.metadata.get('project_id', request.path_params.project_id) }}</dd></div>
</dl>

{% if event.event_type == 'merge_auto_resolved' and diffs %}
  ...
{% endif %}

{% if event.event_type == 'merge_auto_resolved' %}
  <form>...</form>
{% endif %}
```

The template silently drops:
- `event.message` (every event has one)
- the rest of `event.metadata` beyond the single `project_id` lookup
- `event.entity_type`
- `event.verdict`, `event.verdict_notes`, `event.verdicted_by`,
  `event.verdicted_at`

`get_event_detail` in `orch/auto_merge_aggregator.py:278-304` already
returns an `EventRow` carrying all of these (it has `metadata`,
`verdict`, etc. attributes). The route handler at
`dashboard/routers/auto_merge_ui.py:166-239` passes the full event to
the template. So the data is there — the template just doesn't render
it.

The heading at line 4 is hardcoded to `Event #{{ event.id }}`; it
should be a function of `event_type` + timestamp.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/fragments/auto_merge_event_detail.html` | Most event data hidden; opaque heading |
| `dashboard/routers/auto_merge_ui.py` | (optional) compute a human-readable title server-side |
| `dashboard/static/styles.css` | Small new rule for the JSON metadata block |

## Fix Plan

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `frontend-impl` | Expand the modal to render: humanized heading (event_type + timestamp); message; entity_type; full metadata as collapsible pretty-printed JSON (use `<details>`); verdict block (verdict, notes, verdicted_by, verdicted_at) when present. Keep the existing diff section + verdict form for `merge_auto_resolved`. Add a "Copy as JSON" button using `window.iwClipboard.copy(...)`. Append plain CSS rules for the JSON block + scrollable area. | — |
| S02 | `code-review-impl` | Review S01 | — |
| S03 | `tests-impl` | Dashboard tests: each event_type's modal renders `message`, `metadata`, `entity_type`; merge_auto_resolved modal still renders the verdict form. Use the attribute-scoped form for any class checks. | — |
| S04 | `code-review-impl` | Review S03 | — |
| S05 | `code-review-final-impl` | Global review | — |
| S06–S11 | `qv-gate` | lint, format, typecheck, security-sast, unit-tests, integration-tests | — |
| S12 | `qv-browser` | Playwright: open modals for an `auto_merge_health_probe`, `auto_merge_config_updated`, and a `step_launched` event; verify message + metadata are visible | — |
| S13 | `self-assess-impl` | Self-assessment | — |

### Database Changes

None.

### Code Changes

- **Files to modify**:
  - `dashboard/templates/fragments/auto_merge_event_detail.html`
  - `dashboard/static/styles.css` (small block for `.auto-merge-modal__metadata`)
- **Optional / minor**:
  - `dashboard/routers/auto_merge_ui.py` — pass a `humanized_title` string into the template context (cleaner than building it inline in Jinja2).
- **Tests**:
  - `tests/dashboard/test_auto_merge_routes.py` (extend)

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00093_Issue_Design.md` | Design | This document |
| `I-00093_Functional.md` | Design | Human summary |
| `workflow-manifest.json` | Manifest | Steps |
| `prompts/I-00093_S01_Frontend_prompt.md` | Prompt | Modal enrichment |
| `prompts/I-00093_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/I-00093_S03_Tests_prompt.md` | Prompt | Tests |
| `prompts/I-00093_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/I-00093_S05_CodeReview_Final_prompt.md` | Prompt | Final review |
| `prompts/I-00093_S12_BrowserVerification_prompt.md` | Prompt | Playwright verify |
| `prompts/I-00093_S13_SelfAssess_prompt.md` | Prompt | Self-assess |

## Test to Reproduce

```python
def test_event_modal_renders_message_and_metadata_for_health_probe(
    client, db_session, project_factory, daemon_event_factory
):
    project = project_factory(...)
    event = daemon_event_factory(
        project_id=project.id,
        event_type="auto_merge_health_probe",
        message="probe latency 412ms",
        event_metadata={"runtime_reachable": True, "model": "claude-sonnet-4-6", "latency_ms": 412},
    )
    response = client.get(f"/project/{project.id}/auto-merge/events/{event.id}")
    assert response.status_code == 200
    html = response.text

    # Message renders
    assert "probe latency 412ms" in html
    # Metadata keys render
    assert "runtime_reachable" in html
    assert "claude-sonnet-4-6" in html
    assert "412" in html
    # Heading is human-readable (not just 'Event #<id>')
    assert "auto_merge_health_probe" in html  # appears in the title now, not just in the type row
```

Sibling tests cover `auto_merge_config_updated` (asserting `"old"`,
`"new"`, `"updated_by"` are visible), a `merge_auto_resolved` event
(asserting the existing diffs + verdict form still render), and a
plain `step_launched` event (asserting no verdict form appears).

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge"
playwright-cli snapshot                   # find a (view) link ref
playwright-cli click <view-ref>           # open modal
playwright-cli screenshot                 # verify rich content
```

## Acceptance Criteria

### AC1: Modal renders the event message

```
Given any DaemonEvent with non-empty message
When the user opens its detail modal
Then the rendered HTML contains the message text
```

### AC2: Modal renders the metadata as readable JSON

```
Given a DaemonEvent with non-trivial event_metadata
When the user opens its detail modal
Then the rendered HTML contains each top-level metadata key + value
 AND the JSON is presented inside a <details> block (collapsed by default for large payloads)
```

### AC3: Modal heading is humanized

```
Given a DaemonEvent with event_type X and timestamp T
When the user opens its detail modal
Then the heading contains X and a formatted T (not just the numeric id)
```

### AC4: Verdict info renders for merge_auto_resolved events

```
Given a merge_auto_resolved event with verdict='correct', verdict_notes='looked fine', verdicted_by='operator'
When the user opens its detail modal
Then the rendered HTML contains 'correct', 'looked fine', and 'operator'
 AND the existing verdict form still appears with the current selection pre-checked
```

### AC5: No regressions on diffs section

```
Given a merge_auto_resolved event with llm_calls in metadata
When the user opens its detail modal
Then the existing difflib.HtmlDiff diff table renders for each file
```

### AC6: Regression tests exist

All four named tests pass.

## Regression Prevention

- A "render every field" test per event_type class locks down the
  contract.
- The metadata is rendered via a `tojson(indent=2)` filter rather than
  manual key picks, so adding a new metadata key in the daemon does
  not regress display.

## Dependencies

- **Depends on**: None
- **Blocks**: None
- **Conflicts with**: I-00091, I-00092, I-00094, I-00095, I-00096, I-00097 (overlapping auto-merge fragments); run sequentially.

## Impacted Paths

- `dashboard/templates/fragments/auto_merge_event_detail.html`
- `dashboard/static/styles.css`
- `dashboard/routers/auto_merge_ui.py`
- `tests/dashboard/test_auto_merge_routes.py`

## TDD Approach

- Reproducing tests:
  - `tests/dashboard/test_auto_merge_routes.py::test_event_modal_renders_message_and_metadata_for_health_probe`
  - `tests/dashboard/test_auto_merge_routes.py::test_event_modal_renders_old_new_for_config_updated`
  - `tests/dashboard/test_auto_merge_routes.py::test_event_modal_renders_verdict_info_for_resolved`
  - `tests/dashboard/test_auto_merge_routes.py::test_event_modal_no_verdict_form_for_non_resolved_events`
- Assertions are value-specific (I003) and CSS class checks are
  attribute-scoped (I-00067).

## Notes

- 3 of 7 audit incidents.
- The "Copy as JSON" button uses `window.iwClipboard.copy(...)` per
  `dashboard/CLAUDE.md` — NEVER `navigator.clipboard.writeText`.
- The existing modal does NOT call `make css` — plain CSS appended to
  `styles.css` is the right approach.
