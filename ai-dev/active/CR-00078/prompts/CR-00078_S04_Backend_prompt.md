# CR-00078_S04_Backend_prompt

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S04
**Agent**: backend-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
No migration work in this step. The S01 migration applies via the daemon.

## Input Files

- `ai-dev/active/CR-00078/CR-00078_CR_Design.md` (§4 Daemon hook)
- `orch/daemon/batch_manager.py` (lines 440-500 — the existing overlap-gate block)
- `orch/daemon/scope_overlap.py` — pure overlap calculation (do NOT add DB knowledge here)
- `orch/db/models.py` — `BatchOverlapIgnore` model added by S01

## Output Files

- A new helper, location:
  - **Preferred**: `orch/daemon/overlap_ignore.py` (new module, pure helper + DB-query wrapper)
  - OR: `orch/daemon/scope_overlap.py` if and only if you can keep DB-free purity (helper only — the DB query lives in `batch_manager.py`).
- `orch/daemon/batch_manager.py` — call site
- `ai-dev/active/CR-00078/reports/CR-00078_S04_Backend_report.md`

## Requirements

### 1. Pure helper

Add `filter_blocked_by_ignores(blocked_by, ignored_pairs)`:

```python
def filter_blocked_by_ignores(
    blocked_by: list[tuple[str, list[str]]],
    ignored_pairs: set[tuple[str, str]],
) -> list[tuple[str, list[str]]]:
    """Return blocked_by with ignored (blocking_item_id, file_pattern) pairs removed.

    - For each (blocking_id, globs) tuple, drop each glob whose
      (blocking_id, glob) is in `ignored_pairs`.
    - Tuples whose globs list becomes empty are dropped from the result.
    - Pure: no DB access, no I/O. String equality match on the glob.
    """
```

Place this helper wherever you decide — but it MUST be importable from `tests/unit/test_daemon_overlap_filter.py` without dragging in FastAPI / SQLAlchemy session machinery.

### 2. Daemon hook

In `orch/daemon/batch_manager.py`, locate the block at ~line 448-480 (the existing F-00076 scope-overlap gate). After the call to `scope_overlap.find_blocking_items(...)` and **before** the existing `if blocked_by:` branch:

```python
if blocked_by:
    # CR-00078: filter against per-batch ignore set
    ignored_pairs: set[tuple[str, str]] = {
        (row.blocking_item_id, row.file_pattern)
        for row in db.execute(
            select(BatchOverlapIgnore).where(
                BatchOverlapIgnore.project_id == self.project_id,
                BatchOverlapIgnore.batch_id == batch.id,
                BatchOverlapIgnore.held_item_id == item.work_item_id,
            )
        ).scalars()
    }
    filtered_blocked_by = filter_blocked_by_ignores(blocked_by, ignored_pairs)
    if not filtered_blocked_by and ignored_pairs:
        _emit_event(
            db,
            self.project_id,
            "batch_overlap_allowed_by_ignore",
            item.work_item_id,
            "work_item",
            f"Allowed: {item.work_item_id} — all overlaps ignored by operator",
            {
                "candidate_item_id": item.work_item_id,
                "ignored_pairs": [
                    {"blocking_item_id": b, "file_pattern": f}
                    for (b, f) in sorted(ignored_pairs)
                ],
            },
        )
        db.commit()
    # Always narrow blocked_by to the surviving (non-ignored) entries.
    # When every pair was ignored this is [], so the held branch below is
    # skipped and the item falls through to the launch path. When only some
    # pairs were ignored it holds the remainder; when there were no ignores
    # it is unchanged. Forgetting this assignment on the cleared path is the
    # classic bug — the held branch would still see the original non-empty
    # list and the item would never launch.
    blocked_by = filtered_blocked_by

if blocked_by:
    # existing emission of item_held_for_scope per remaining blocking item
    ...
```

Key invariants:
- The ignore query is scoped by **all three of** `project_id`, `batch_id`, `held_item_id` — not by `held_item_id` alone.
- After filtering, `blocked_by` MUST be reassigned to `filtered_blocked_by` on **every** path — cleared-everything, partially-cleared, and no-ignores alike. The cleared-everything path is the trap: emitting the event is not enough; if `blocked_by` is left as the original non-empty list the held branch below still holds the item and it never launches (AC3 would fail).
- The `batch_overlap_allowed_by_ignore` event is emitted only when ignores actually cleared the hold (`not filtered_blocked_by and ignored_pairs`). If the operator hasn't ignored anything yet and the overlap is real, no new event — the existing `item_held_for_scope` emission still fires for the remaining pairs.
- The existing `_emit_overlap_allowed_by_policy_if_needed` branch is unchanged — both policy-allowed and ignore-allowed events can coexist in different scenarios.

### 3. TDD RED for the helper

In `tests/unit/test_daemon_overlap_filter.py`:

1. **RED**: Write a failing test for `filter_blocked_by_ignores`. Suggested first case: empty `ignored_pairs` returns input unchanged (identity). Run the test before implementing the helper to capture `ImportError: cannot import name 'filter_blocked_by_ignores' ...` as `tdd_red_evidence`.
2. **GREEN**: implement the helper.
3. **REFACTOR**: tighten typing.

The remaining unit-test cases (full ignore, partial ignore, glob-with-string-equality) are owned by S10 — your job here is one RED case for the helper to satisfy `tdd_red_evidence`.

## Project Conventions

- Read `orch/CLAUDE.md` for daemon module structure, sync SQLAlchemy patterns, and the `DaemonEvent.metadata` → `event_metadata` reserved-name gotcha.
- The existing `_emit_event` helper in `batch_manager.py` is the canonical event-emission pattern — match it exactly. Do not introduce a new helper. Locate it with `grep -n 'def _emit_event' orch/daemon/batch_manager.py`; its signature is `(db, project_id, event_type, entity_id, entity_type=None, message=None, metadata=None)` and the caller commits.

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

```bash
uv run pytest tests/unit/test_daemon_overlap_filter.py::test_empty_ignores_returns_input -v
```

Just that one test — the rest are owned by S10. Do NOT run `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "backend-impl",
  "work_item": "CR-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/overlap_ignore.py (or orch/daemon/scope_overlap.py)",
    "orch/daemon/batch_manager.py",
    "tests/unit/test_daemon_overlap_filter.py (single RED case to anchor tdd_red_evidence)"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "1 passed (test_empty_ignores_returns_input)",
  "tdd_red_evidence": "tests/unit/test_daemon_overlap_filter.py::test_empty_ignores_returns_input — ImportError: cannot import name 'filter_blocked_by_ignores' from 'orch.daemon.overlap_ignore'",
  "blockers": [],
  "notes": "Decided helper location: <chose new module or extended scope_overlap.py>"
}
```
