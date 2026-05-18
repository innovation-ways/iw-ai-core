# I-00095_S01_Backend_prompt

**Work Item**: I-00095 — Auto-merge events table columns are not sortable
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies — `docs/IW_AI_Core_Agent_Constraints.md`. No alembic.

## Input Files

- `uv run iw item-status I-00095 --json`
- `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- `ai-dev/active/I-00095/I-00095_Functional.md`
- `orch/auto_merge_aggregator.py`
- `orch/db/models.py` (DaemonEvent + MergeAutoVerdict shape)
- `tests/unit/test_auto_merge_aggregator.py`
- `orch/CLAUDE.md`, `CLAUDE.md`

## Output Files

- `ai-dev/active/I-00095/reports/I-00095_S01_Backend_report.md`

## Context

`list_recent_events` always orders by `created_at DESC`. Add a
whitelist-driven sort parameter so the route can honour user-requested
ordering safely.

## Requirements

### 1. Extend `list_recent_events`

In `orch/auto_merge_aggregator.py:list_recent_events`, add two
parameters:

```python
def list_recent_events(
    db: Session,
    project_id: str,
    *,
    page: int = 0,
    page_size: int = 50,
    event_type_filter: str | None = None,
    sort: str = "created_at",      # new
    direction: str = "desc",       # new
) -> tuple[list[EventRow], int]:
```

Define a module-level whitelist:

```python
SORTABLE_COLUMNS: dict[str, ColumnElement[Any]] = {
    "created_at": DaemonEvent.created_at,
    "event_type": DaemonEvent.event_type,
    "entity_id": DaemonEvent.entity_id,
    "verdict": MergeAutoVerdict.verdict,
}
```

Note: `verdict` lives on the OUTER JOIN table — when sorting by
verdict, rows without a verdict will collate either first or last
depending on Postgres `NULLS FIRST/LAST` default; explicitly choose
`NULLS LAST` so unverdicted rows fall to the bottom in either
direction.

Validation:

```python
if sort not in SORTABLE_COLUMNS:
    raise ValueError(f"sort must be one of {sorted(SORTABLE_COLUMNS)}; got {sort!r}")
if direction not in ("asc", "desc"):
    raise ValueError(f"direction must be 'asc' or 'desc'; got {direction!r}")
```

Apply:

```python
col = SORTABLE_COLUMNS[sort]
order = col.asc() if direction == "asc" else col.desc()
if sort == "verdict":
    order = order.nulls_last()
stmt = stmt.order_by(order)
```

Default values keep existing behaviour for callers that don't pass
sort/direction.

### 2. Do NOT change `get_event_detail` or other functions

Out of scope.

### 3. Update aggregator unit tests for the signature change

The existing tests that call `list_recent_events` continue to work
unchanged (the new params have defaults). Do NOT pre-write the new
sort tests here — those belong to S07. Your only test edit here is
the RED test for the new sort param:

```python
def test_list_recent_events_sorts_by_event_type_asc(db_session, project_factory, daemon_event_factory):
    project = project_factory(project_id="p-i00095-asc")
    for event_type in ("auto_merge_health_probe",
                       "auto_merge_config_updated",
                       "merge_auto_resolved"):
        daemon_event_factory(project_id=project.id, event_type=event_type, message="x")
    rows, _ = list_recent_events(db_session, project.id, sort="event_type", direction="asc")
    types = [r.event_type for r in rows]
    assert types == sorted(types), f"Expected ascending event_type sort; got {types}"
```

This is your RED evidence — record the failing run output in
`tdd_red_evidence`.

### 4. Do NOT add the route-level rejection here

Returning 400 on bad `sort=message` is S03's job (the route layer).
This function raises `ValueError`; the route translates that to an
HTTPException.

## Project Conventions

- `orch/CLAUDE.md` — SQLAlchemy 2.0 declarative style. Use
  `Mapped[]`-style references already in the module.
- `psycopg` v3 driver. No raw string SQL — use SQLAlchemy column
  expressions.
- No `importlib.reload(orch.config)` in tests.

## TDD Requirement (RED → GREEN)

Backend step — RED first:

1. Write `test_list_recent_events_sorts_by_event_type_asc` first; run
   it; capture the AssertionError (events come back in created_at
   desc order, NOT alphabetical).
2. Implement `sort`/`direction` per Requirement 1.
3. Re-run the targeted test; capture GREEN.

```bash
uv run pytest tests/unit/test_auto_merge_aggregator.py::test_list_recent_events_sorts_by_event_type_asc -v
```

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Targeted:

```bash
uv run pytest tests/unit/test_auto_merge_aggregator.py -v
```

Do NOT run `make test-unit`.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00095",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/auto_merge_aggregator.py",
    "tests/unit/test_auto_merge_aggregator.py"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_auto_merge_aggregator.py::test_list_recent_events_sorts_by_event_type_asc — AssertionError: Expected ascending event_type sort; got ['merge_auto_resolved', 'auto_merge_config_updated', 'auto_merge_health_probe']  // captured RED run",
  "blockers": [],
  "notes": "Note any decision on NULLS LAST for verdict sort."
}
```
