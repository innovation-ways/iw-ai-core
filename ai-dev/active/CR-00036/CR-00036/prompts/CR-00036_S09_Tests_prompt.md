# CR-00036_S09_Tests_prompt

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
**Step**: S09
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md` — Acceptance Criteria AC1-AC10, AC11a, AC11b.
- All prior step reports under `ai-dev/work/CR-00036/reports/`.
- `tests/CLAUDE.md` — testcontainer rules and fixture conventions.
- `tests/conftest.py` — `db_session` fixture and FTS bootstrap.

## Output Files

- `ai-dev/work/CR-00036/reports/CR-00036_S09_Tests_report.md`

## Context

You are filling in test coverage for CR-00036. Per-step impl agents (S01, S03, S05, S07) wrote the *minimum* tests required to support TDD. Your job is to add the cross-cutting and end-to-end tests that prove the full happy path and the documented acceptance criteria.

Read the design doc's "TDD Approach" and "Acceptance Criteria" sections carefully — they enumerate what must be covered.

## Requirements

### 1. End-to-end gate test

`tests/integration/test_merge_queue_auto_merge_gate.py` (new):

- **Scenario A (auto_merge=true, baseline)**: Build a Batch with `auto_merge=True`, a single approved WorkItem with one workflow step. Drive the daemon's BatchManager to completion. Assert: BatchItem reaches `merging` and then `merged` without manual intervention; `awaiting_merge_approval` was never observed.
- **Scenario B (auto_merge=false, gate engages)**: Same setup but `auto_merge=False`. Drive workflow steps to success. Assert:
  1. BatchItem.status is `awaiting_merge_approval` (not `completed`, not `merging`).
  2. `process_merge_queue` does NOT pick the item up (call it explicitly; assert no merge attempt was made).
  3. No `merging`, `merged`, `merge_failed` state was reached.
  4. The BatchItem's worktree is still alive (worktree_info still present).
- **Scenario C (manual approval releases the gate)**: From state B, call `approve_merge(db, project_id, item_id)`. Then call `process_merge_queue`. Assert: BatchItem transitions through `merging` to `merged` (mocking the executor script per existing test pattern in `tests/integration/test_merge_queue_*.py`).
- **Scenario D (failed item bypasses gate)**: With `auto_merge=False`, drive an item to `failed` (e.g., last step fails). Assert: BatchItem.status terminates in `failed`, never enters `awaiting_merge_approval`.

### 2. CLI happy path

`tests/integration/test_cli_items.py` (new or extended):

- `iw item approve-merge` happy path: BatchItem in `awaiting_merge_approval` → exit 0, status now `completed`.
- Rejection: BatchItem in any other status → exit 4, status unchanged.
- JSON mode emits the documented payload.

### 3. CLI batch-create flag matrix

`tests/integration/test_cli_batches.py` (extended):

- Default with project `auto_merge=true` (or absent) → Batch row has `auto_merge=True`.
- Default with project `auto_merge=false` → Batch row has `auto_merge=False`.
- Explicit `--auto-merge` overrides project default `false` → `True`.
- Explicit `--no-auto-merge` overrides project default `true` → `False`.

Use a fixture that monkeypatches the registry parser or feeds a temporary `projects.toml`.

### 4. Dashboard rendering

`tests/dashboard/test_item_overview_awaiting_merge.py` (new — confirm S07 didn't already create it; if so, extend):

- BatchItem in `awaiting_merge_approval` → response HTML contains the Merge button (search for the htmx attribute `hx-post="/actions/item/{id}/approve-merge"`).
- BatchItem in `merge_failed` → response HTML contains Restart Merge but NOT the new Merge button.
- BatchItem in `completed` → no Merge button.
- BatchItem in `merging` → no Merge button.

`tests/dashboard/test_batch_detail_auto_merge_toggle.py` (extended):

- Toggle is rendered with `checked` when `batch.auto_merge=True`.
- Toggle is rendered without `checked` when `batch.auto_merge=False`.
- Toggle is enabled when batch.status in `planning|approved|paused`.
- Toggle is disabled (HTML `disabled` attribute) when batch.status in `executing|completed|...`.

### 5. Endpoint coverage

`tests/integration/test_dashboard_actions.py` (extended): cover any branches not exercised by S05's RED tests:

- `approve-merge` against item in `merging` → 409.
- `approve-merge` against item in `merged` → 409.
- `update_batch_auto_merge` happy path (planning → toggle off → row updated).
- `update_batch_auto_merge` 409 on batch in `executing`.

### 6. Enum-iteration regression check

Update `tests/integration/test_entity_type_classification.py` (or wherever `BatchItemStatus` is iterated) to ensure `awaiting_merge_approval` is included in any all-statuses-tested loops.

### 7. Acceptance-criteria mapping

In your S09 report, include a section "AC coverage matrix" with one row per AC1..AC10, AC11a, AC11b listing the test file + function that covers it. ACs without a corresponding test must be flagged in `notes` with a short justification (e.g., AC11b covered by `test_batch_detail_auto_merge_toggle.py::test_toggle_disabled_when_running`).

## Project Conventions

Read `tests/CLAUDE.md`:

- NEVER connect tests to live DB — use testcontainers only.
- After `Base.metadata.create_all()`, run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`.
- psycopg2 → psycopg URL replacement (`url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`).
- Don't `importlib.reload(orch.config)` — use `monkeypatch.delenv()` instead.

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

The full `make test-unit && make test-integration && make test-dashboard` suite MUST pass. Do NOT report `tests_passed: true` unless every counter is zero failures.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "tests-impl",
  "work_item": "CR-00036",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X unit, Y integration, Z dashboard, 0 failed",
  "blockers": [],
  "notes": ""
}
```
