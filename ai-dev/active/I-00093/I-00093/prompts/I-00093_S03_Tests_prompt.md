# I-00093_S03_Tests_prompt

**Work Item**: I-00093 — Auto-merge event detail modal hides the most useful fields
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00093 --json`
- `ai-dev/active/I-00093/I-00093_Issue_Design.md` — MANDATORY (Test to
  Reproduce, AC, TDD Approach)
- `ai-dev/active/I-00093/reports/I-00093_S01_Frontend_report.md`
- `dashboard/templates/fragments/auto_merge_event_detail.html` (post-S01)
- `dashboard/routers/auto_merge_ui.py`
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`
- `tests/dashboard/conftest.py`
- `tests/integration/auto_merge_fixtures.py`

## Output Files

- `ai-dev/active/I-00093/reports/I-00093_S03_Tests_report.md`

## Context

S01 enriched the modal to render message, metadata, entity_type,
verdict block, and a humanized heading. You write regression tests
covering each event_type's contract.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

- BAD: `assert "Message" in html` (heading word — passes against bug)
- BAD: `assert "metadata" in html` (lowercase appears in many places)
- GOOD: `assert "<exact message string the factory set>" in html`
- GOOD: `assert "runtime_reachable" in html` (a key the factory put in
  metadata that wouldn't appear elsewhere)

## Requirements

### 1. Test: health probe modal renders message + metadata

```python
def test_event_modal_renders_message_and_metadata_for_health_probe(
    client, db_session, project_factory, daemon_event_factory
):
    project = project_factory(...)
    event = daemon_event_factory(
        project_id=project.id,
        event_type="auto_merge_health_probe",
        message="probe latency 412ms",
        event_metadata={
            "runtime_reachable": True,
            "model": "claude-sonnet-4-6",
            "cli_tool": "claude-code",
            "latency_ms": 412,
        },
    )
    response = client.get(f"/project/{project.id}/auto-merge/events/{event.id}")
    assert response.status_code == 200
    html = response.text

    assert "probe latency 412ms" in html, "message must render"
    assert "runtime_reachable" in html, "metadata key must render"
    assert "claude-sonnet-4-6" in html, "metadata value must render"
    assert "412" in html, "numeric metadata value must render"
```

### 2. Test: config_updated modal renders old + new

```python
def test_event_modal_renders_old_new_for_config_updated(
    client, db_session, project_factory, daemon_event_factory
):
    project = project_factory(...)
    event = daemon_event_factory(
        project_id=project.id,
        event_type="auto_merge_config_updated",
        message="auto-merge config updated from dashboard",
        event_metadata={
            "old": {"phase": None, "runtime_option_id": 4},
            "new": {"phase": 1, "runtime_option_id": None},
            "updated_by": "dashboard",
            "source": "dashboard",
        },
    )
    response = client.get(f"/project/{project.id}/auto-merge/events/{event.id}")
    assert response.status_code == 200
    html = response.text

    assert "auto-merge config updated from dashboard" in html
    # JSON rendering: keys are visible
    assert "old" in html
    assert "new" in html
    assert "updated_by" in html
    assert "dashboard" in html
```

### 3. Test: verdict info renders for a resolved event with a verdict

```python
def test_event_modal_renders_verdict_info_for_resolved(
    client, db_session, project_factory, daemon_event_factory, merge_verdict_factory
):
    project = project_factory(...)
    event = daemon_event_factory(
        project_id=project.id,
        event_type="merge_auto_resolved",
        message="resolved 1 conflict in tests/foo.py",
        event_metadata={"llm_calls": []},
    )
    merge_verdict_factory(
        project_id=project.id, daemon_event_id=event.id,
        verdict="correct", verdict_notes="looked fine", verdicted_by="operator",
    )
    response = client.get(f"/project/{project.id}/auto-merge/events/{event.id}")
    html = response.text

    assert "correct" in html
    assert "looked fine" in html
    assert "operator" in html
    # Existing verdict form still appears with the value pre-selected
    assert 'name="verdict"' in html
    assert 'value="correct"' in html
```

### 4. Test: no verdict form on non-resolved events

```python
def test_event_modal_no_verdict_form_for_non_resolved_events(
    client, db_session, project_factory, daemon_event_factory
):
    project = project_factory(...)
    event = daemon_event_factory(
        project_id=project.id,
        event_type="step_launched",
        message="Step S13 launched (PID 99)",
        event_metadata={"pid": 99, "step_id": 13},
    )
    response = client.get(f"/project/{project.id}/auto-merge/events/{event.id}")
    html = response.text

    # Verdict form must NOT appear
    assert 'name="verdict"' not in html
    # But the message and metadata still must appear
    assert "Step S13 launched (PID 99)" in html
    assert "pid" in html
    assert "99" in html
```

### 5. Test: humanized heading

```python
def test_event_modal_heading_is_humanized(
    client, db_session, project_factory, daemon_event_factory
):
    project = project_factory(...)
    event = daemon_event_factory(
        project_id=project.id, event_type="auto_merge_health_probe",
        message="ok", event_metadata={"runtime_reachable": True},
    )
    response = client.get(f"/project/{project.id}/auto-merge/events/{event.id}")
    html = response.text

    # Heading contains the event_type (was previously "Event #<id>" only)
    # Scope to the <h3>:
    import re
    heading = re.search(r'<h3[^>]*id="auto-merge-event-title"[^>]*>(.*?)</h3>', html, re.DOTALL)
    assert heading, "heading element must exist"
    heading_text = heading.group(1)
    assert "auto_merge_health_probe" in heading_text
```

### 6. Required helpers / factories

If `daemon_event_factory` or `merge_verdict_factory` don't already
exist in `tests/integration/auto_merge_fixtures.py` (or in the shared
`tests/dashboard/conftest.py`), add them following the existing factory
pattern in the codebase. They MUST commit a real DB row using the test
session (no mocks — see CLAUDE.md "NEVER mock the database in
integration tests" — TestClient-backed dashboard tests use a real
testcontainer too).

### 7. Test placement

All five tests live under `tests/dashboard/` because they use the
`client` fixture (I-00067).

### 8. CSS class assertions

If any test asserts on a CSS class (e.g.
`auto-merge-modal__metadata`), use the attribute-scoped form
(I-00067):

```python
assert re.search(r'class\s*=\s*"[^"]*\bauto-merge-modal__metadata\b[^"]*"', html)
```

## Project Conventions

- `tests/CLAUDE.md`.
- No live DB connections.
- No `importlib.reload(orch.config)`.

## TDD Requirement

Coverage step — `tdd_red_evidence = "n/a — coverage step (tests-impl)"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

Do NOT run the full suite.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00093",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_auto_merge_routes.py",
    "tests/integration/auto_merge_fixtures.py"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — coverage step (tests-impl)",
  "blockers": [],
  "notes": ""
}
```
