# I-00117_S03_Tests_prompt

**Work Item**: I-00117 -- Daemon silently dead-ends a non-fixable, non-retryable failed step
**Step**: S03 — Reproduction + regression tests
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. The ONLY allowed docker usage is via `testcontainers` pytest
fixtures (they self-label under Ryuk and self-destruct). Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00117/I-00117_Issue_Design.md` (Test to Reproduce + AC1-AC3)
- `ai-dev/active/I-00117/reports/I-00117_S01_Backend_report.md`
- Reference patterns: `tests/integration/test_fix_cycle.py`, `tests/CLAUDE.md`,
  `tests/conftest.py` (fixtures: `pg_engine`, `db_session`, `test_project`).

## Output Files

- New test file: `tests/integration/test_recovery_exhausted_escalation.py`
- `ai-dev/active/I-00117/reports/I-00117_S03_Tests_report.md`

## Requirements

Write an **integration** test (real PostgreSQL testcontainer — FOR UPDATE locking
and status transitions cannot be mocked; see `tests/CLAUDE.md`). Follow the
testcontainer + FTS-DDL rules in `tests/CLAUDE.md`.

### 1. Reproduction test (AC1)

`test_exhausted_implementation_step_escalates_visibly`:
- Seed a project, work item (`in_progress`), batch + batch item (`executing`), and
  an `implementation` `WorkflowStep` in `failed` status with **two** `StepRun`
  rows (retries exhausted) whose latest failure reason does **NOT** start with
  `SPEC_MISMATCH:` (e.g. `"Blocked: out-of-scope gate failure"`).
- Invoke the daemon's failed-step handler for that batch item (drive the same
  entry point `batch_manager` uses; follow how `test_fix_cycle.py` constructs the
  manager / calls the handler).
- Assert **semantic, specific** values:
  - `work_item.status == WorkItemStatus.failed`
  - `batch_item.status == BatchItemStatus.failed`
  - exactly one `DaemonEvent` with `entity_id == "<item>"` and
    `event_type == "step_recovery_exhausted"` exists
  - that event's `event_metadata["step_id"]` equals the failed step's id

### 2. Regression test (AC2)

`test_spec_mismatch_still_routes_to_its_own_handler`:
- Same seeding but the latest failure reason starts with `SPEC_MISMATCH:`.
- Assert a `spec_mismatch_escalation` event is emitted and **no**
  `step_recovery_exhausted` event is emitted (the two paths are mutually
  exclusive).

### 3. Structural guard

Add an assertion (in the repro test or a third test) that after the handler runs
on a failed non-recoverable step, the work item is in a **terminal** status
(`status not in {in_progress}`) — pins the invariant that this path never returns
silently.

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Tests must verify SPECIFIC VALUES, not just shape:
- BAD: `assert events` / `assert len(events) > 0`
- GOOD: `assert any(e.event_type == "step_recovery_exhausted" for e in events)`
- GOOD: `assert work_item.status == WorkItemStatus.failed` (not just "not in_progress" alone)

## Test Verification (NON-NEGOTIABLE)

Run ONLY the new file: `uv run pytest tests/integration/test_recovery_exhausted_escalation.py -v`.
**DO NOT** run `make test-integration` or `make test-unit` — full-suite execution
is owned by the downstream QV gates (`unit-tests`, `integration-tests`). Do not
report `tests_passed: true` unless your targeted run is green.

Do NOT revert source files at runtime to "prove RED" — that is a design-time
exercise. If you want RED evidence, temporarily comment your own new assertion,
not the production fix.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00117",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/test_recovery_exhausted_escalation.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (targeted)",
  "tdd_red_evidence": "tests/integration/test_recovery_exhausted_escalation.py::test_exhausted_implementation_step_escalates_visibly — <RED failure line captured against pre-fix branch behavior or commented assertion>",
  "blockers": [],
  "notes": ""
}
```
