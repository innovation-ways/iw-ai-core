# CR-00078_S06_API_prompt

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S06
**Agent**: api-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
No migration work in this step.

## Input Files

- `ai-dev/active/CR-00078/CR-00078_CR_Design.md` (§2, §3, §4, §5, AC1-AC6)
- `dashboard/routers/batches.py` (GET endpoint from CR-00077, Timeline rendering)
- `dashboard/routers/actions.py` (existing POST-style endpoints for batch + item operations — the home for these new POSTs)
- `orch/db/models.py` (`BatchOverlapIgnore`, `DaemonEvent`)

## Output Files

- `dashboard/routers/actions.py` — new POST endpoints
- `dashboard/routers/batches.py` — modify GET overlap endpoint to filter ignored files; extend Timeline rendering
- `ai-dev/active/CR-00078/reports/CR-00078_S06_API_report.md`

## Requirements

### 1. POST `/project/{project_id}/batch/{batch_id}/overlap/{held_item_id}/ignore`

Form/htmx body fields:
- `blocking_item_id: str` (required)
- `file_pattern: str` (required)
- `reason: str | None` (optional)

Behaviour:
1. Resolve project + verify the batch + batch-item exist (404 otherwise).
2. Insert one `BatchOverlapIgnore` row using `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing(...)` — this gives idempotency without a try/except wrapper. Pass `index_elements=["project_id", "batch_id", "held_item_id", "blocking_item_id", "file_pattern"]` so PG matches the composite PK.
3. Set `ignored_by="operator"` with a `# TODO(auth): replace placeholder when session subjects land` comment on the line.
4. Emit a `batch_overlap_ignored_by_operator` `DaemonEvent` row with `entity_type="work_item"`, `entity_id=held_item_id`, and `event_metadata={"candidate_item_id": held_item_id, "blocking_item_id": ..., "file_pattern": ..., "reason": reason_or_null, "ignored_by": "operator"}`. Use the existing `_emit_event` helper if one is exported from `orch/daemon/batch_manager.py` — if not, write a small inline call against `DaemonEvent`.
5. `db.commit()`.
6. Return `HTMLResponse("")` with status 200. The htmx `outerHTML` swap on `closest .iw-modal-file-row` removes the row.

### 2. POST `/project/{project_id}/batch/{batch_id}/overlap/{held_item_id}/ignore-all`

No body fields required.

Behaviour:
1. Resolve project / batch / batch-item.
2. Query the most recent `item_held_for_scope` `DaemonEvent` rows for this `(project_id, held_item_id)` within the same 300s window used by CR-00077 (`_get_scope_statuses` — reuse the constant / helper).
3. Build the deduped set of `(blocking_item_id, file_pattern)` pairs from the events' `event_metadata["conflicting_globs"]` — same grouping logic as CR-00077's `group_overlap_events`.
4. Insert one `BatchOverlapIgnore` row per pair (one bulk `insert(...).on_conflict_do_nothing()` or a loop — either is fine; bulk is preferred). `reason` stays NULL.
5. Emit a single `batch_overlap_ignore_all_by_operator` `DaemonEvent` with `event_metadata={"candidate_item_id": held_item_id, "count": N, "pairs": [{"blocking_item_id": ..., "file_pattern": ...}, ...]}` where N is the number of pairs (NOT the number of inserts — the count is based on the input set, idempotency-safe).
6. `db.commit()`.
7. Return `HTMLResponse("")` with status 200. The htmx `innerHTML` swap on `#overlap-modal-root` closes the modal.

### 3. Modify GET `/project/{project_id}/batch/{batch_id}/overlap/{held_item_id}`

In `dashboard/routers/batches.py`, the endpoint added by CR-00077:

After fetching the recent events and BEFORE calling `group_overlap_events`, query the `BatchOverlapIgnore` table for `(project_id, batch_id, held_item_id)`, build a set of `(blocking_item_id, file_pattern)` tuples. Pass that set into the grouping (or filter the events' `conflicting_globs` lists before grouping).

Result:
- A `(blocking_item_id, glob)` pair already in `BatchOverlapIgnore` does NOT appear in any section's file list.
- A section whose entire glob list is ignored does NOT appear at all.
- If after filtering there are no sections, the modal returns the same empty/404 fragment from CR-00077.

### 4. Extend Timeline rendering

In whichever function in `dashboard/routers/batches.py` renders Timeline event rows (look for `item_held_for_scope` references — there is one near line 158 per earlier exploration; the surrounding function iterates `DaemonEvent` rows and produces row data), add a branch for each of the 3 new event types per CR-00078 §5:

| event_type | message template |
|---|---|
| `batch_overlap_ignored_by_operator` | `f"Operator ignored overlap on {file_pattern} with {blocking_item_id} (held: {held_item_id})"` |
| `batch_overlap_ignore_all_by_operator` | `f"Operator ignored all {count} remaining overlaps for {held_item_id}"` |
| `batch_overlap_allowed_by_ignore` | `f"{candidate_item_id} launched — ignored overlaps with {blocking_ids}"` |

Pull each value from `event_metadata` defensively (`.get(...)`); if a key is missing, fall back to a sensible string like `"(unknown)"` rather than raising.

### 5. Route mounting

Mount the two POST endpoints in `dashboard/routers/actions.py` using the existing routing patterns (most `/actions/...` style endpoints in this file return HTML fragments; match that). If the existing file naming convention prefers `/actions/...` over `/project/.../overlap/...`, follow the existing convention — read the file's first 50 lines to decide.

## Project Conventions

- Read `dashboard/CLAUDE.md`: routers are thin, htmx posts return HTML fragments.
- `dashboard/dependencies.py:get_db()` for the session.
- Match the existing batch-action endpoint signatures in `actions.py` (e.g., `approve_batch`, `pause_batch`).

## TDD Requirement

The full endpoint behavioural tests are S10's. Your job is the implementation. Set `tdd_red_evidence` to: `"n/a — endpoint implementation step; behavioural tests in S10 (tests/dashboard/test_batch_overlap_ignore_endpoints.py)."`

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

Run a targeted pytest on any one existing actions test to confirm you didn't break route registration:

```bash
uv run pytest tests/dashboard/test_actions.py -v -k batch
```

Adjust the `-k` filter to whatever batch-action tests exist in the repo. Do NOT run the full `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "api-impl",
  "work_item": "CR-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/actions.py",
    "dashboard/routers/batches.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "<N> passed on targeted actions tests",
  "tdd_red_evidence": "n/a — endpoint implementation; behavioural tests owned by S10",
  "blockers": [],
  "notes": "Mounted endpoints under <chosen prefix>; idempotency via INSERT ON CONFLICT DO NOTHING."
}
```
