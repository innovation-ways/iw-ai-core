# I-00090_S03_Tests_prompt

**Work Item**: I-00090 -- `/system/running` "Failed / Needs Attention" and "Recently Completed" tables show steps from inactive work items
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Testcontainer fixtures (started by `tests/conftest.py` / dashboard
`conftest.py`) are exempt — they self-label and self-destruct via Ryuk.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT generate or modify any alembic migration. Do not run
alembic upgrade/downgrade/stamp from your shell.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00090 --json`
- `ai-dev/active/I-00090/I-00090_Issue_Design.md` -- Design document (read § "TDD Approach" in full — every numbered test below is mandatory)
- `ai-dev/active/I-00090/I-00090_Functional.md` -- Functional summary
- `ai-dev/active/I-00090/reports/I-00090_S01_Backend_report.md` -- S01 report (what was changed)
- `dashboard/routers/running.py` -- the file under test (post-S01)
- `tests/dashboard/conftest.py` -- registers the `client` fixture used by route-level tests
- `tests/conftest.py` -- registers `db_session` (testcontainer-backed) and `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` constants
- `tests/dashboard/test_docs_running_jobs.py` -- a reference test in the same dir (look at its `client` fixture pattern)
- `orch/db/models.py` -- for `Project`, `WorkItem`, `WorkflowStep`, `StepRun`, `WorkItemStatus`, `WorkItemPhase`, `WorkItemType`, `StepStatus`, `RunStatus`
- `skills/iw-ai-core-testing/SKILL.md` -- IW-AI-Core testing standards; assertion-strength rules and live-DB write guard

## Output Files

- `tests/dashboard/test_running_router_active_filter.py` -- new test file
- `ai-dev/active/I-00090/reports/I-00090_S03_Tests_report.md` -- Step report

## Context

You are writing the reproduction + regression test coverage for **I-00090**. The Backend step (S01) has already applied the active-item predicate to `_query_failed_steps()` and `_query_recent_completions()` in `dashboard/routers/running.py`. Your job is to write the test file that:

1. **Reproduces the bug** — at least one test that would FAIL against pre-S01 code and PASSES against the current (fixed) code.
2. **Locks in the regression coverage** — every WorkItem-status branch (in_progress, completed, cancelled, archived, failed, paused) for BOTH helpers, plus a route-level smoke test for both routes.

## Requirements

### 1. Create the test file at the correct location

Path: `tests/dashboard/test_running_router_active_filter.py`

**WHY tests/dashboard/ and not tests/integration/**: the dashboard `client` fixture is registered only in `tests/dashboard/conftest.py`. A test placed under `tests/integration/` that requests the `client` fixture fails with `fixture 'client' not found` (I-00067 lesson). The helper-level tests don't need `client`, but co-locating them with the route-level tests in a single file keeps the test surface cohesive and matches the precedent set by `tests/dashboard/test_docs_running_jobs.py`.

The file MUST have a module-level docstring identifying the work item, e.g.:

```python
"""I-00090 — Tests for the active-item filter on /system/running.

The dashboard's `/system/running` page (and `/project/{id}/running`) must only
surface failed/completed step rows for work items that are *currently active*
— i.e. WorkItem.archived_at IS NULL AND WorkItem.status NOT IN (completed,
cancelled). Items in draft/approved/in_progress/paused/failed status DO
surface (item-level `failed` is unresolved).

See ai-dev/active/I-00090/I-00090_Issue_Design.md.
"""
```

### 2. Write helper-level tests for `_query_failed_steps()` (8 tests)

Each test creates a Project, one or more WorkItems with the relevant status/archived state, one or more WorkflowStep rows with `status=failed` or `needs_fix`, and asserts on the rows returned by `_query_failed_steps(db_session)` directly.

Tests required (all 8 MUST be present — the design's TDD Approach section lists them):

1. `test_query_failed_steps_includes_in_progress_item` — `status=in_progress`, `archived_at=None` → item id appears in returned rows
2. `test_query_failed_steps_excludes_completed_item` — `status=completed` → item id does NOT appear  **← this is the REPRODUCTION test (RED on pre-S01, GREEN after)**
3. `test_query_failed_steps_excludes_cancelled_item` — `status=cancelled` → item id does NOT appear
4. `test_query_failed_steps_excludes_archived_item` — `archived_at=<now>` (any status, suggest `in_progress` to make the point that archive alone is sufficient) → item id does NOT appear
5. `test_query_failed_steps_includes_failed_item` — `status=failed`, `archived_at=None` → item id appears (item-level `failed` is unresolved)
6. `test_query_failed_steps_includes_paused_item` — `status=paused`, `archived_at=None` → item id appears
7. `test_query_failed_steps_includes_needs_fix_status` — step.status=`needs_fix` on an `in_progress` item → row appears (regression guard for the OR in `status.in_([failed, needs_fix])`)
8. `test_query_failed_steps_respects_project_filter` — two projects each with one active+failed item; `_query_failed_steps(db_session, project_id="p1")` returns only `p1`'s row

### 3. Write helper-level tests for `_query_recent_completions()` (6 tests)

Each test seeds a `WorkItem`, a `WorkflowStep`, and a `StepRun` row with `status=RunStatus.completed` and `completed_at = now()` (well within the 1-hour cutoff). No `needs_fix` mirror — `_query_recent_completions` does not filter by step.status.

Tests required (all 6 MUST be present):

9. `test_query_recent_completions_includes_in_progress_item`
10. `test_query_recent_completions_excludes_completed_item`  **← also a REPRODUCTION case for AC3**
11. `test_query_recent_completions_excludes_cancelled_item`
12. `test_query_recent_completions_excludes_archived_item`
13. `test_query_recent_completions_includes_failed_item`
14. `test_query_recent_completions_includes_paused_item`

### 4. Write route-level smoke tests (2 tests)

Use the dashboard `client` fixture from `tests/dashboard/conftest.py`.

15. `test_system_running_route_renders_active_item_only`:
    - Seed two failed steps in one project: one on an item `I-ALIVE` (status=in_progress, archived_at=None), one on an item `I-DEAD` (status=completed, archived_at=None).
    - `response = client.get("/system/running")`
    - Assert `response.status_code == 200`.
    - Assert `"I-ALIVE"` IS in `response.text`.
    - Assert `"I-DEAD"` is NOT in `response.text`.
16. `test_project_running_route_renders_active_item_only`:
    - Same seed as above, plus a SECOND project with its own active+failed item.
    - `GET /project/{project_a.id}/running`
    - Assert `200`, project-A's active item appears, project-B's item does NOT (regression guard for project filter), and the dead item from project A does NOT.

### 5. Use realistic, semantically-strong assertions

**CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)**

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "failed" in response.text` (shape only — matches almost any page on the dashboard)
- BAD: `assert len(rows) > 0` then nothing else
- BAD: `assert len(rows) == 1` (brittle to seed changes, says nothing about which row)
- GOOD: `assert "I-DEAD" not in [r.item_id for r in rows]`
- GOOD: `assert "I-ALIVE" in response.text and "I-DEAD" not in response.text`
- GOOD: `assert any(r.item_id == "I-ALIVE" and r.step_id == "S01" for r in rows)`

For the route-level smoke tests, the item-id strings are unique tokens — `assert "I-ALIVE" in response.text` is semantically strong because the token cannot collide with surrounding boilerplate. The CSS-class-name false-positive risk (I-00067) does not apply because we're asserting on data, not on class attributes.

### 6. Helper factory functions — DRY but explicit

You will be creating many `Project` / `WorkItem` / `WorkflowStep` / `StepRun` rows. Add small private helpers at the top of the test file, e.g.:

```python
def _make_project(db, pid: str = "p1") -> Project: ...
def _make_item(db, pid: str, iid: str, *, status: WorkItemStatus, archived: bool = False) -> WorkItem: ...
def _make_step(db, pid: str, iid: str, sid: str, *, status: StepStatus) -> WorkflowStep: ...
def _make_run(db, step_id: int, *, status: RunStatus, completed_at: datetime | None = None) -> StepRun: ...
```

Each helper MUST commit (`db.add(...); db.flush()` or `db.commit()` — pattern-match the existing dashboard tests).

Pay attention to model required fields:
- `WorkItem` requires `project_id`, `id`, `type` (`WorkItemType.ChangeRequest` or `.Issue`), `title`, `status`, `phase`. Look at `tests/dashboard/test_docs_running_jobs.py` for a reference seed pattern.
- `WorkflowStep` requires `project_id`, `work_item_id`, `step_id`, `agent_label`, `status`, `step_number`.
- `StepRun` requires `step_id` (the integer PK of WorkflowStep, NOT the "S01" string), `status`, `run_number`, and for completed runs `completed_at` and (optionally) `duration_secs`.

When you're not sure what a required field is, run a quick `grep -n "class WorkItem\|class WorkflowStep\|class StepRun" orch/db/models.py` and read the model declaration.

### 7. No mocking of the database

This is an integration-level test exercising real SQLAlchemy queries. Use the `db_session` fixture from `tests/conftest.py` (testcontainer-backed Postgres). Do NOT mock `db.execute()` or stub `Session`.

### 8. No connection to the live DB

The `db_session` fixture is testcontainer-only. Do NOT import `orch.db.session.SessionLocal` directly in your tests — that points at port 5433 (the production orchestration DB). The live-DB write guard in `tests/conftest.py` will hard-fail your test if you do.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

This rule applies to EVERY assertion in this test file. Reviewers will flag shape-only assertions as a HIGH finding.

## Project Conventions

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, `tests/CLAUDE.md`, and especially `skills/iw-ai-core-testing/SKILL.md` for:

- Test naming conventions (`test_<verb>_<expected>` or `test_<thing>_<scenario>_<result>`)
- Fixture patterns (`db_session`, dashboard `client`)
- The live-DB write guard and why it matters
- Cross-project isolation patterns
- pytest-randomly resilience (no test should depend on another test's seed)

## TDD Requirement

You are the dedicated coverage step. Follow this order:

1. **RED**: Write `test_query_failed_steps_excludes_completed_item` FIRST. Run it with:
   ```bash
   uv run pytest tests/dashboard/test_running_router_active_filter.py::test_query_failed_steps_excludes_completed_item -v
   ```
   It should PASS (because S01 has already applied the fix). To verify it would have FAILED on pre-S01 code, reason about it textually in your report — describe why the assertion `assert "CR-DEAD" not in [r.item_id for r in rows]` would fail before the predicate was added (because the unfiltered query returns CR-DEAD's row).

   ⚠️ Do NOT revert, stash, or comment out previously-shipped source files at runtime to "observe RED". Pre-fix reproduction is a design-time exercise (the design author already proved the bug exists on `main`; see `evidences/pre/`). Runtime source-revert workflows cause thrash, dirty worktrees, and timeouts, and are explicitly prohibited by `iw-review-design`.
2. **GREEN**: Add the remaining tests, run them — all should pass (the fix is already in place).
3. **REFACTOR**: Extract the seed helpers, tidy the file, ensure no test depends on another's state.

Do NOT skip the RED phase. Your `tdd_red_evidence` field MUST record a 1-line textual reasoning statement, e.g.: `"reasoning: assertion 'CR-DEAD' not in [r.item_id for r in rows] would fail against pre-S01 code because the unfiltered _query_failed_steps returns CR-DEAD's row"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. **`make format`** — auto-fix any drift in your new file.
2. **`make typecheck`** — must report zero errors involving your new test file.
3. **`make lint`** — must report zero errors.

## Test Verification (NON-NEGOTIABLE)

After implementation, run ONLY the new test file:

```bash
uv run pytest tests/dashboard/test_running_router_active_filter.py -v
```

All 16 tests MUST pass. Do **NOT** run `make test-integration` or `make test-unit` — those are gates S11/S12.

If any of your targeted tests fail, fix them before reporting completion.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_running_router_active_filter.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "16 passed, 0 failed",
  "tdd_red_evidence": "<actual snippet OR 1-line reasoning per the TDD Requirement section>",
  "blockers": [],
  "notes": ""
}
```

- `tests-impl` is a dedicated coverage step and is EXEMPT from the "RED-first behavioural test" gate in the reviewer's checklist 5a. But your `tdd_red_evidence` is still required and should capture the textual reasoning sentence.
- `files_changed` should contain exactly the new test file.
