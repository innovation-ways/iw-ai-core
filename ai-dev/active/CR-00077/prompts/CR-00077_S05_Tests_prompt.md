# CR-00077_S05_Tests_prompt

**Work Item**: CR-00077 -- Overlap details popup (read-only)
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits
(Standard policy. Testcontainers in pytest fixtures are exempt.)

## ⛔ Migrations: agents generate, daemon applies
No migration file should be created by this step.

## Input Files

- `ai-dev/active/CR-00077/CR-00077_CR_Design.md`
- `ai-dev/active/CR-00077/reports/CR-00077_S01_API_report.md`
- `ai-dev/active/CR-00077/reports/CR-00077_S03_Frontend_report.md`
- `tests/CLAUDE.md`, `tests/conftest.py`, `skills/iw-ai-core-testing/SKILL.md` — testing rules.

## Output Files

- `tests/unit/test_batch_overlap_grouping.py` (new)
- `tests/dashboard/test_batch_overlap_modal.py` (new)
- `ai-dev/active/CR-00077/reports/CR-00077_S05_Tests_report.md`

## Requirements

### 1. `tests/unit/test_batch_overlap_grouping.py`

Pure unit tests for `group_overlap_events` (imported from `dashboard.routers.batches`).

Required test cases — each MUST use exact-value assertions (no `assert result` / no `assert len(result) > 0`):

1. **Empty list** → returns `[]`.
2. **Single event** → returns `[("CR-00076", ["a.py", "b.py"])]`. Assert both the id and the exact globs list.
3. **Duplicate blocking_item_id, most-recent-wins** → input `[event_new("CR-00076", ["new"]), event_old("CR-00076", ["old"])]` (events ordered newest-first) → result is `[("CR-00076", ["new"])]`. Assert payload is "new", not "old".
4. **Two distinct blocking items, order preserved** → input ordered `[event_A, event_B]` returns `[A, B]`; input ordered `[event_B, event_A]` returns `[B, A]`.
5. **Missing `event_metadata` key** → an event row whose `event_metadata` is `None` or lacks `blocking_item_id`/`conflicting_globs` is silently skipped; the function does not raise. Build a row that triggers each branch and assert the resulting tuple list omits it.

For each test, capture the RED failure first (you can run the targeted test before the helper exists or after deliberately breaking it). Record `tdd_red_evidence`.

### 2. `tests/dashboard/test_batch_overlap_modal.py`

Integration tests using the dashboard TestClient + the `db_session` testcontainer fixture from `tests/conftest.py`.

Required test cases — every assertion uses exact substring matches against the rendered HTML (NOT `assert response.status_code == 200` alone, which is vacuous):

1. **Happy path — grouped sections rendered**
   - Seed: a `Project` (slug `p1`), two `WorkItem` rows (`CR-99001` held + `CR-99002` blocking) with realistic `title`, a `Batch` and `BatchItem` linking the held item, two `DaemonEvent` rows of `event_type='item_held_for_scope'`, `entity_type='work_item'`, `entity_id='CR-99001'`, `created_at=now()`, `event_metadata={"candidate_item_id":"CR-99001","blocking_item_id":"CR-99002","conflicting_globs":["docs/Foo.md","skills/x/**","ai-dev/work/Y.md"]}`. (Two events with two distinct blocking ids to exercise the grouping.)
   - `client.get("/project/p1/batch/BATCH-99001/overlap/CR-99001")` → status 200.
   - Assert body contains the blocking_item_id strings.
   - Assert body contains EVERY glob from EVERY seeded payload (loop over globs and `assert glob in response.text`).
   - Assert body contains `href="/project/p1/item/CR-99002"`.
   - Assert body contains `Overlap details — CR-99001`.
   - Assert response **does not** contain `<html` or `<body` (it is a fragment).
   - Assert body **does not** contain `<form`, `hx-post`, or `hx-delete` (AC6 — the modal is read-only; CR-00078 owns the write actions). S06 verifies this assertion is present.

2. **404 path — no recent event**
   - Seed: same Project + Batch + BatchItem, but NO `DaemonEvent` rows.
   - `client.get(...)` → status **404**.
   - Assert body contains `No overlap details available`.
   - Assert body does NOT contain `<html` or `<body`.

3. **Window cutoff** (regression guard for the 300s window)
   - Seed one `DaemonEvent` with `created_at = now() - 301 seconds`.
   - `client.get(...)` → status 404 (event is outside the window).
   - Assert body contains `No overlap details available`.

### 3. TDD RED evidence

For each new test file, capture an `AssertionError` (or `ImportError` for the helper before it exists) and paste the failing line into `tdd_red_evidence`. Do NOT report `tests_passed: true` if any of the new tests was never observed failing.

### 4. Targeted runs only

```bash
uv run pytest tests/unit/test_batch_overlap_grouping.py -v
uv run pytest tests/dashboard/test_batch_overlap_modal.py -v
```

Do NOT run `make test-unit` or `make test-integration` here — those are the QV gates' job.

## Project Conventions

- Read `tests/CLAUDE.md`: testcontainers only (port 5433 is forbidden for tests); FTS triggers must be installed in test DB; `metadata` → `event_metadata` for `DaemonEvent`.
- Use the existing `db_session` fixture from `tests/conftest.py` (it handles testcontainer + `Base.metadata.create_all()` + FTS triggers).
- Use existing helpers / fixtures from `tests/dashboard/` for the TestClient. Match the seeding style of `tests/dashboard/test_batches_*.py` (find one and copy its skeleton).

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint` (includes `make test-assertions` indirectly via `make quality` — but you don't need to run `make quality` here)

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "CR-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_batch_overlap_grouping.py",
    "tests/dashboard/test_batch_overlap_modal.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "<X> passed, 0 failed across both files",
  "tdd_red_evidence": "tests/unit/test_batch_overlap_grouping.py::test_two_distinct_items_order_preserved — AssertionError: assert [('B', ...), ('A', ...)] == [('A', ...), ('B', ...)] // captured RED before implementing the helper fix",
  "blockers": [],
  "notes": ""
}
```
