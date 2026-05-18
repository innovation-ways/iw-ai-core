# I-00095_S07_Tests_prompt

**Work Item**: I-00095 — Auto-merge events table columns are not sortable
**Step**: S07
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00095 --json`
- `ai-dev/active/I-00095/I-00095_Issue_Design.md` — Test to Reproduce
  + AC + TDD Approach (MANDATORY read)
- All three implementation reports (S01, S03, S05)
- `orch/auto_merge_aggregator.py` (post-S01)
- `dashboard/routers/auto_merge_ui.py` (post-S03)
- `dashboard/templates/fragments/auto_merge_events_table.html` (post-S05)
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`
- `tests/dashboard/conftest.py`
- `tests/integration/auto_merge_fixtures.py`

## Output Files

- `ai-dev/active/I-00095/reports/I-00095_S07_Tests_report.md`

## Context

You write the regression suite for sortable columns across unit and
dashboard layers.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

- BAD: `assert "sort" in html`
- BAD: `assert "asc" in html` (lowercase "asc" appears in many places)
- GOOD: `assert 'sort=event_type' in href` extracted from a specific
  `<button hx-get>`
- GOOD: `assert response.status_code == 400 and "sort must be one of" in response.text`

## Requirements

### 1. Unit: aggregator sort behaviour

```python
def test_list_recent_events_sorts_by_event_type_asc(db_session, project_factory, daemon_event_factory):
    """Already added in S01 — keep here as canonical reference."""
    ...

def test_list_recent_events_sorts_by_event_type_desc(db_session, project_factory, daemon_event_factory):
    ...

def test_list_recent_events_sorts_by_entity_id_asc(db_session, project_factory, daemon_event_factory):
    ...

def test_list_recent_events_sorts_by_verdict_nulls_last(db_session, project_factory, daemon_event_factory, merge_verdict_factory):
    """Verdict sort puts unverdicted rows after verdicted rows in both directions."""
    ...

def test_list_recent_events_rejects_unknown_sort_column(db_session, project_factory):
    project = project_factory(project_id="p-reject-1")
    with pytest.raises(ValueError, match="sort must be one of"):
        list_recent_events(db_session, project.id, sort="message")
    with pytest.raises(ValueError, match="sort must be one of"):
        list_recent_events(db_session, project.id, sort="actions")
    with pytest.raises(ValueError, match="direction must be"):
        list_recent_events(db_session, project.id, direction="random")
```

### 2. Dashboard: route param validation

```python
def test_invalid_sort_param_returns_400(client, project_factory):
    project = project_factory(...)
    response = client.get(
        f"/project/{project.id}/auto-merge/events?page=0&page_size=10&sort=message"
    )
    assert response.status_code == 400
    assert "sort must be one of" in response.text  # message from HTTPException

def test_invalid_dir_param_returns_400(client, project_factory):
    project = project_factory(...)
    response = client.get(
        f"/project/{project.id}/auto-merge/events?page=0&page_size=10&dir=random"
    )
    assert response.status_code == 400
```

### 3. Dashboard: rendered header is a sortable button

```python
def test_table_header_renders_clickable_sort_button_for_timestamp(client, project_factory):
    project = project_factory(...)
    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=10")
    html = response.text

    import re
    # The 'timestamp' header is a <button hx-get …sort=created_at…>
    match = re.search(
        r'<button\b[^>]*\bhx-get="[^"]*\bsort=created_at\b[^"]*"[^>]*>\s*timestamp\b',
        html,
    )
    assert match, f"timestamp header should be a sortable button; got:\n{html[:2000]}"
```

### 4. Dashboard: chevron + aria-sort on active column

```python
def test_active_column_carries_chevron_and_aria_sort(client, project_factory):
    project = project_factory(...)
    response = client.get(
        f"/project/{project.id}/auto-merge/events?page=0&page_size=10&sort=event_type&dir=asc"
    )
    html = response.text

    # The event_type column has aria-sort="ascending"
    import re
    assert re.search(
        r'<th\b[^>]*\baria-sort="ascending"[^>]*>\s*<button[^>]*>event_type',
        html,
    )
    # Chevron ↑ appears next to event_type
    assert re.search(r'event_type\s*<span[^>]*>↑</span>', html)
    # Other sortable columns DON'T carry aria-sort
    assert html.count('aria-sort=') == 1
```

### 5. Dashboard: filter + sort + pagination interoperate

```python
def test_filter_and_sort_combine_correctly(client, project_factory, daemon_event_factory):
    project = project_factory(...)
    for _ in range(60):
        daemon_event_factory(project_id=project.id, event_type="auto_merge_health_probe", message="x")
    response = client.get(
        f"/project/{project.id}/auto-merge/events"
        "?page=0&page_size=50&type=auto_merge_health_probe&sort=created_at&dir=asc"
    )
    html = response.text
    # Pagination Next link carries ALL three: type, sort, dir
    import re
    next_btn = re.search(
        r'<(?:button|a)\b[^>]*\bhx-get="([^"]*page=1[^"]*)"[^>]*>\s*Next',
        html,
    )
    assert next_btn, "Next button missing"
    next_url = next_btn.group(1)
    assert "type=auto_merge_health_probe" in next_url
    assert "sort=created_at" in next_url
    assert "dir=asc" in next_url
```

### 6. Test placement

- Unit tests under `tests/unit/test_auto_merge_aggregator.py`.
- Dashboard tests under `tests/dashboard/test_auto_merge_routes.py`.
- The `client` fixture is registered only in
  `tests/dashboard/conftest.py` (I-00067).

### 7. CSS assertions

If asserting CSS class names use the attribute-scoped form (I-00067).

## Project Conventions

- `tests/CLAUDE.md`.
- No live DB connections.
- No `importlib.reload(orch.config)`.

## TDD Requirement

Coverage step — `tdd_red_evidence = "n/a — coverage step (tests-impl)"`.
S01 carries the RED evidence for the underlying aggregator change.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_auto_merge_aggregator.py tests/dashboard/test_auto_merge_routes.py -v
```

Do NOT run `make test-unit`/`make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "I-00095",
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
