# I-00068_S01_Backend_prompt

**Work Item**: I-00068 -- Recent Activity batch link from "archived" event routes to /item/ instead of /batch/
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch Alembic migrations — it modifies a Python helper signature and call sites only.

## Input Files

- `uv run iw item-status I-00068 --json` — runtime step state
- `ai-dev/active/I-00068/I-00068_Issue_Design.md` — Design document (READ FIRST)
- `ai-dev/active/I-00068/I-00068_Functional.md` — Functional design
- `ai-dev/active/I-00068/evidences/pre/I-00068-snapshot.yml` — Pre-fix accessibility snapshot showing the asymmetric URL bug
- `orch/archive/batch_archiver.py` — File containing the buggy `_emit` (current lines 341-357)
- `orch/db/models.py` — `DaemonEvent` model (note: `metadata` is `event_metadata` in Python)
- `orch/cli/batch_commands.py` line 392 — Reference: how `entity_type="batch"` is set correctly elsewhere
- `orch/daemon/batch_manager.py` — Reference: another correct pattern (`_emit_event` threads entity_type through)
- `orch/CLAUDE.md` and `CLAUDE.md` — Project conventions (especially `event_metadata` gotcha and append-only `daemon_events`)

## Output Files

- `ai-dev/active/I-00068/reports/I-00068_S01_Backend_report.md` — Step report

## Context

You are implementing the backend half of the fix for I-00068. The bug: `orch/archive/batch_archiver.py:341-357` defines a private `_emit(...)` helper that constructs a `DaemonEvent` without setting `entity_type`. Every event emitted by `archive_batch` (e.g., `batch_archived`, `batch_archive_failed`) is therefore stored with `entity_type=None`, which breaks the dashboard's link routing for batch IDs.

Read the design doc end-to-end before writing any code, especially the Root Cause Analysis and Acceptance Criteria sections.

## Requirements

### 1. Add an entity_type parameter to _emit

In `orch/archive/batch_archiver.py`:

- Modify the `_emit(...)` function signature to accept an `entity_type: str | None = None` keyword argument.
- Pass `entity_type=entity_type` to the `DaemonEvent(...)` constructor.
- Default `None` keeps the function backward-compatible if any other caller exists (sweep with `grep` to verify; today, all call sites are within `batch_archiver.py`).

### 2. Update every batch-archive call site to pass entity_type="batch"

Within `orch/archive/batch_archiver.py`, find every place that calls `_emit(...)`. For each call that is emitting a BATCH-scoped event (i.e., `entity_id` is a batch ID like `BATCH-XXXXX`), pass `entity_type="batch"`.

Use `grep -n "_emit(" orch/archive/batch_archiver.py` to enumerate them. Common event types in this file include `batch_archived`, `batch_archive_failed`, `batch_archive_started`. Every one of them is a batch event — they all need `entity_type="batch"`.

### 3. Do NOT modify other modules

Do NOT touch `orch/daemon/batch_manager.py`, `orch/cli/batch_commands.py`, `orch/cli/step_commands.py`, `orch/daemon/merge_queue.py`, `orch/cli/merge_queue_commands.py`, or any other emitter. The scope of this incident is limited to the archiver per operator decision (see Notes section in the design doc).

### 4. Preserve the append-only contract

Do NOT add updates or deletes to existing `daemon_events` rows — `daemon_events` is append-only (see `orch/CLAUDE.md`). Historical rows with `entity_type=None` will continue to exist; the dashboard hardening in S03 handles them.

### 5. Type hints and consistency

- `entity_type` parameter: `str | None = None` (matching the column type in `DaemonEvent`).
- Place the new parameter consistently with the helper's existing parameter order (after `metadata` if it makes sense, or wherever it reads naturally — match neighbouring emitter helpers in `orch/daemon/main.py`, `orch/daemon/merge_queue.py`, `orch/daemon/doc_job_poller.py`, `orch/daemon/batch_manager.py`).

## Project Conventions

Read `orch/CLAUDE.md` for:

- SQLAlchemy 2.0 sync ORM (`Mapped[]`)
- `event_metadata` Python attribute name for the `metadata` column (SQLAlchemy reserves `metadata`)
- Append-only `daemon_events` (no UPDATE / DELETE)

Read `CLAUDE.md` for project-wide rules.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: In a scratch test (or directly in the new file `tests/integration/test_i00068_batch_link_routing.py`), write a unit/integration test that calls `batch_archiver._emit(...)` and asserts the resulting `DaemonEvent.entity_type == "batch"`. Run it — it MUST FAIL on the current (pre-fix) code.
2. **GREEN**: Make the changes above so the test passes.
3. **REFACTOR**: Clean up.

Do NOT skip the RED phase. The test must exist and fail before the implementation change. (S05 will write the full regression suite; your RED test can be a stub that S05 absorbs or a focused unit test you keep.)

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

```bash
make format
make typecheck
make lint
```

All three must report no new violations involving the files you touched.

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration` and `make test-unit`. Both must pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00068",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/archive/batch_archiver.py",
    "tests/integration/test_i00068_batch_link_routing.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
