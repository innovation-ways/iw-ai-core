# I-00097_S03_Tests_prompt

**Work Item**: I-00097 — Auto-merge polish — token cost formatting & entity_id linkification
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00097 --json`
- `ai-dev/active/I-00097/I-00097_Issue_Design.md`
- `ai-dev/active/I-00097/reports/I-00097_S01_Frontend_report.md`
- The two modified templates
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`
- `tests/dashboard/conftest.py`

## Output Files

- `ai-dev/active/I-00097/reports/I-00097_S03_Tests_report.md`

## Context

Regression tests for the two polish changes.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

- BAD: `assert "$" in html` (passes against the bug)
- BAD: `assert "CR-00057" in html` (the string appears even when not
  linked)
- GOOD: `assert "$0.000000" not in html and "$0" in html` (for the
  exact rendering)
- GOOD: regex-scope the entity_id cell and assert it contains an
  `<a href="/project/.../item/CR-00057">` tag (singular `item`)

## Requirements

### 1. Token cost zero formatting

```python
def test_token_cost_zero_renders_as_dollar_zero(client, project_factory):
    project = project_factory(...)
    response = client.get(f"/project/{project.id}/auto-merge/rollup?window=7d")
    html = response.text
    assert "$0.000000" not in html, "exact zero must not render with 6 decimal places"
    # Look for '$0' in a context that is clearly the cost line
    import re
    cost_line = re.search(r'<p\b[^>]*>\s*in:\s*\d+\s*·\s*out:\s*\d+\s*·\s*\$(\S+)\s*</p>', html)
    assert cost_line, f"cost line not found in:\n{html[:1000]}"
    assert cost_line.group(1) == "0", f"expected '$0'; got '${cost_line.group(1)}'"
```

### 2. Token cost non-zero keeps precision

```python
def test_token_cost_nonzero_keeps_precision(client, project_factory, daemon_event_factory):
    """Seed an event with llm_calls metadata that produces a small non-zero cost."""
    project = project_factory(...)
    # MODEL_PRICING includes claude-sonnet-4-6 at $3/M in, $15/M out.
    # Seed 1000 input tokens and 100 output tokens of sonnet → cost = 0.003 + 0.0015 = 0.0045
    daemon_event_factory(
        project_id=project.id,
        event_type="merge_auto_resolved",
        message="x",
        event_metadata={"llm_calls": [{
            "model": "claude-sonnet-4-6",
            "input_tokens": 1000,
            "output_tokens": 100,
        }]},
    )
    response = client.get(f"/project/{project.id}/auto-merge/rollup?window=7d")
    html = response.text
    import re
    cost_line = re.search(r'in:\s*\d+\s*·\s*out:\s*\d+\s*·\s*\$(\S+)\s*</p>', html)
    assert cost_line
    val = cost_line.group(1)
    # Allow either trimmed-zero form ("0.0045") or full precision ("0.004500")
    # depending on S01's implementation choice. The MUST is: no trailing zeros
    # past the meaningful digits when implementation chose to trim.
    assert not val.endswith("000000"), f"trailing zeros not trimmed; got '${val}'"
```

(If S01 chose NOT to trim trailing zeros for non-zero values — i.e.
only specialised the zero case — this test will still pass for
`"0.004500"`; only assert the value is non-`"0"`.)

### 3. entity_id link for work-item IDs

```python
def test_entity_id_renders_as_link_for_work_item_ids(client, project_factory, daemon_event_factory):
    project = project_factory(project_id="iw-ai-core")
    daemon_event_factory(
        project_id=project.id,
        event_type="step_launched",
        entity_id="CR-00057",
        message="step launched",
    )
    # If I-00096 has landed, default view excludes step_launched — use ?all=1
    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=10&all=1")
    html = response.text
    import re
    # Scope: a single entity_id cell that contains the link
    assert re.search(
        r'<a\b[^>]*\bhref="/project/iw-ai-core/item/CR-00057"[^>]*>\s*CR-00057\s*</a>',
        html,
    ), f"entity_id should be a link; got snippet:\n{html[:2000]}"
```

### 4. entity_id plain text for non-work-item IDs

```python
def test_entity_id_renders_plain_when_not_work_item_id(client, project_factory, daemon_event_factory):
    project = project_factory(project_id="iw-ai-core")
    daemon_event_factory(
        project_id=project.id,
        event_type="auto_merge_config_updated",
        entity_id="iw-ai-core",  # project_id, not a work item
        message="config updated",
    )
    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=10")
    html = response.text
    import re
    # 'iw-ai-core' must NOT be wrapped in an /item/ link
    assert not re.search(r'href="/project/[^"]+/item/iw-ai-core"', html)
    # But it must still appear as text in the entity_id column
    assert "iw-ai-core" in html
```

### 5. entity_id '—' for null

```python
def test_entity_id_renders_dash_when_null(client, project_factory, daemon_event_factory):
    project = project_factory(...)
    daemon_event_factory(
        project_id=project.id,
        event_type="auto_merge_health_probe",
        entity_id=None,
        message="probe",
    )
    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=10")
    html = response.text
    # The fragment renders '—' for null entity_id. Scope to the entity_id cell.
    # A row with entity_id=NULL should still have a <td>—</td> in the column.
    import re
    assert re.search(r'<td[^>]*\bfont-mono\b[^>]*>\s*—\s*</td>', html), (
        "entity_id cell should render '—' for null"
    )
```

### 6. Test placement

All under `tests/dashboard/` (uses `client` fixture — I-00067).

## Project Conventions

`tests/CLAUDE.md`. Attribute-scoped CSS class assertions only.

## TDD Requirement

Coverage step — `tdd_red_evidence = "n/a — coverage step (tests-impl)"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Targeted only:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00097",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/dashboard/test_auto_merge_routes.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — coverage step (tests-impl)",
  "blockers": [],
  "notes": ""
}
```
