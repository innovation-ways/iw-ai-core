# I-00096_S07_Tests_prompt

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Step**: S07
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00096 --json`
- `ai-dev/active/I-00096/I-00096_Issue_Design.md`
- Step reports from S01, S03, S05
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`
- `tests/dashboard/conftest.py`

## Output Files

- `ai-dev/active/I-00096/reports/I-00096_S07_Tests_report.md`

## Context

You write regression tests for chip dedup AND the auto-merge-only
default filter AND the show-all toggle.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

- BAD: `assert "auto-merge-status-chip" in html`
- GOOD: `assert html.count('id="auto-merge-status-chip"') == 1`
- BAD: `assert "Show all" in html`
- GOOD: extract the `<button class="auto-merge-show-all-toggle">` and
  assert its `aria-pressed` matches the expected state

## Requirements

### 1. Unit: aggregator default + opt-out

```python
def test_list_recent_events_default_excludes_non_auto_merge(db_session, project_factory, daemon_event_factory):
    """Already added in S03 RED; keep canonical here."""
    ...

def test_list_recent_events_include_non_auto_merge_shows_everything(db_session, project_factory, daemon_event_factory):
    project = project_factory(project_id="p-i00096-include")
    daemon_event_factory(project_id=project.id, event_type="step_launched", message="x")
    daemon_event_factory(project_id=project.id, event_type="auto_merge_health_probe", message="probe")
    rows, _ = list_recent_events(db_session, project.id, include_non_auto_merge=True)
    types = {r.event_type for r in rows}
    assert "step_launched" in types
    assert "auto_merge_health_probe" in types

def test_list_recent_events_explicit_event_type_filter_overrides_prefix_default(db_session, project_factory, daemon_event_factory):
    """When user picks a single event_type filter, that takes precedence — even if it's a non-auto-merge type (which we still serve so the chip set works)."""
    project = project_factory(project_id="p-i00096-explicit")
    daemon_event_factory(project_id=project.id, event_type="step_launched", message="x")
    rows, _ = list_recent_events(db_session, project.id, event_type_filter="step_launched")
    assert len(rows) == 1
    assert rows[0].event_type == "step_launched"
```

### 2. Dashboard: exactly one chip on /auto-merge

```python
def test_auto_merge_page_renders_exactly_one_chip(client, project_factory):
    project = project_factory(...)
    response = client.get(f"/project/{project.id}/auto-merge")
    html = response.text
    assert html.count('id="auto-merge-status-chip"') == 1, (
        f"Expected exactly one chip; found {html.count('id=\"auto-merge-status-chip\"')}"
    )
```

### 3. Dashboard: topbar chip still appears on other pages

```python
def test_topbar_chip_appears_on_non_auto_merge_page(client, project_factory, auto_merge_config_factory):
    project = project_factory(...)
    # Need phase >= 1 for the topbar chip to render at all
    auto_merge_config_factory(project_id=project.id, phase=1)
    response = client.get(f"/project/{project.id}/queue")
    assert response.status_code == 200
    # The compact chip uses auto-merge-chip--compact class
    import re
    assert re.search(
        r'class\s*=\s*"[^"]*\bauto-merge-chip--compact\b[^"]*"',
        response.text,
    ), "Topbar compact chip should appear on /queue"
```

### 4. Dashboard: default events view excludes non-auto-merge

```python
def test_default_events_view_excludes_non_auto_merge(client, project_factory, daemon_event_factory):
    project = project_factory(...)
    daemon_event_factory(project_id=project.id, event_type="step_launched", message="step-x")
    daemon_event_factory(project_id=project.id, event_type="auto_merge_health_probe", message="probe-y")

    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=50")
    html = response.text

    assert "probe-y" in html, "auto-merge event should appear"
    assert "step-x" not in html, "non-auto-merge event must NOT appear in default view"
```

### 5. Dashboard: ?all=1 includes non-auto-merge

```python
def test_show_all_toggle_includes_non_auto_merge_events(client, project_factory, daemon_event_factory):
    project = project_factory(...)
    daemon_event_factory(project_id=project.id, event_type="step_launched", message="step-x")
    daemon_event_factory(project_id=project.id, event_type="auto_merge_health_probe", message="probe-y")

    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=50&all=1")
    html = response.text

    assert "probe-y" in html
    assert "step-x" in html
```

### 6. Dashboard: Show-all toggle button is present and reflects state

```python
def test_show_all_toggle_button_renders_with_correct_aria_pressed(client, project_factory):
    project = project_factory(...)
    # Default
    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=50")
    import re
    btn = re.search(
        r'<button\b[^>]*\bclass="[^"]*\bauto-merge-show-all-toggle\b[^"]*"[^>]*>',
        response.text,
    )
    assert btn, "show-all toggle button must render"
    assert 'aria-pressed="false"' in btn.group(0)

    # With all=1
    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=50&all=1")
    btn = re.search(
        r'<button\b[^>]*\bclass="[^"]*\bauto-merge-show-all-toggle\b[^"]*"[^>]*>',
        response.text,
    )
    assert btn
    assert 'aria-pressed="true"' in btn.group(0)
```

### 7. Test placement

Unit under `tests/unit/`; dashboard under `tests/dashboard/`.

### 8. CSS class assertions are attribute-scoped (I-00067).

## Project Conventions

`tests/CLAUDE.md`. No live DB.

## TDD Requirement

Coverage step — `tdd_red_evidence = "n/a — coverage step (tests-impl)"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Targeted only:

```bash
uv run pytest tests/unit/test_auto_merge_aggregator.py tests/dashboard/test_auto_merge_routes.py -v
```

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "I-00096",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_auto_merge_aggregator.py",
    "tests/dashboard/test_auto_merge_routes.py"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed across unit/dashboard, 0 failed",
  "tdd_red_evidence": "n/a — coverage step (tests-impl)",
  "blockers": [],
  "notes": ""
}
```
