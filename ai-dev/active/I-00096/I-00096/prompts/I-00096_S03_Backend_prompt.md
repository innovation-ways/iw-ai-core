# I-00096_S03_Backend_prompt

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies — no docker, no alembic.

## Input Files

- `uv run iw item-status I-00096 --json`
- `ai-dev/active/I-00096/I-00096_Issue_Design.md`
- `orch/auto_merge_aggregator.py`
- `tests/unit/test_auto_merge_aggregator.py`
- `orch/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00096/reports/I-00096_S03_Backend_report.md`

## Context

`list_recent_events` queries every `DaemonEvent` for the project,
which floods the auto-merge page with `step_launched` etc. Restrict
to auto-merge prefixes by default; allow opt-out for "Show all".

## Requirements

### 1. Module-level constant for prefixes

In `orch/auto_merge_aggregator.py`, add near the top:

```python
AUTO_MERGE_EVENT_PREFIXES: tuple[str, ...] = ("auto_merge_", "merge_auto_")
```

This is the explicit, auditable source of truth. Adding a new
auto-merge event type that follows the convention shows up
automatically; events that don't follow the convention can be added
manually (but that's a separate decision).

### 2. Extend `list_recent_events`

Add a new keyword-only parameter:

```python
def list_recent_events(
    db: Session,
    project_id: str,
    *,
    page: int = 0,
    page_size: int = 50,
    event_type_filter: str | None = None,
    include_non_auto_merge: bool = False,  # new
    sort: str = "created_at",          # if I-00095 has landed
    direction: str = "desc",           # if I-00095 has landed
) -> tuple[list[EventRow], int]:
```

(If I-00095 has not landed at S03 time, omit the `sort`/`direction`
params and the I-00096 fix is independent.)

### 3. Apply the prefix filter

When `event_type_filter is None` AND `include_non_auto_merge is False`,
add a filter clause:

```python
from sqlalchemy import or_

if event_type_filter is None and not include_non_auto_merge:
    stmt = stmt.where(
        or_(*(DaemonEvent.event_type.like(p + "%") for p in AUTO_MERGE_EVENT_PREFIXES))
    )
```

When `event_type_filter` is set, that takes precedence (the user
explicitly picked a single event type). When `include_non_auto_merge`
is True, no prefix filter applies.

### 4. RED-first unit test

Write the failing test in `tests/unit/test_auto_merge_aggregator.py`:

```python
def test_list_recent_events_default_excludes_non_auto_merge(db_session, project_factory, daemon_event_factory):
    project = project_factory(project_id="p-i00096-1")
    daemon_event_factory(project_id=project.id, event_type="step_launched", message="x")
    daemon_event_factory(project_id=project.id, event_type="auto_merge_health_probe", message="probe")
    rows, _ = list_recent_events(db_session, project.id)
    types = {r.event_type for r in rows}
    assert "step_launched" not in types
    assert "auto_merge_health_probe" in types
```

Run it pre-implementation → it fails (default includes step_launched).
Capture for `tdd_red_evidence`.

### 5. Do NOT change `get_event_detail`, `get_status_snapshot`, etc.

Those are unrelated.

## Project Conventions

`orch/CLAUDE.md`; SQLAlchemy 2.0 declarative. Use `or_(*list)` rather
than chaining `.where` for OR conditions.

## TDD Requirement (RED → GREEN)

Backend behavioural step — capture RED before implementing.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_auto_merge_aggregator.py -v
```

Do NOT run `make test-unit`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "I-00096",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/auto_merge_aggregator.py",
    "tests/unit/test_auto_merge_aggregator.py"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_auto_merge_aggregator.py::test_list_recent_events_default_excludes_non_auto_merge — AssertionError: 'step_launched' should not be in default view  // captured RED run",
  "blockers": [],
  "notes": ""
}
```
