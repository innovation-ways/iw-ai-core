# I-00104_S03_Tests_prompt

**Work Item**: I-00104 -- Batch planner false-negative overlap analysis + Max Parallel display mismatch
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits
(Testcontainers in pytest fixtures are exempt.)

## ⛔ Migrations: agents generate, daemon applies
No migration files in this step.

## Input Files

- `ai-dev/active/I-00104/I-00104_Issue_Design.md` (Acceptance Criteria AC1..AC5)
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`
- `tests/conftest.py` (db_session fixture)
- `tests/dashboard/conftest.py` (client fixture)
- `orch/batch_planner.py` (the new code to test)
- `dashboard/routers/actions.py` (the `create_batch_from_selection` endpoint — `POST /batch/create-from-selection`)

## Output Files

- `tests/unit/test_batch_planner_overlap.py` — new
- `tests/dashboard/test_batch_plan_max_parallel.py` — new
- `ai-dev/active/I-00104/reports/I-00104_S03_Tests_report.md`

## Requirements

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For I-00104 specifically:
- BAD: `assert analysis["A"].overlap_with` (truthy check — passes even if it's `[]` after a bug regression because of falsy-list confusion in some refactors)
- GOOD: `assert "B" in analysis["A"].overlap_with` (semantic — verifies the expected ID is present)
- BAD: `assert "Max Parallel" in plan_md` (substring — passes even when value is wrong)
- GOOD: `assert "**Max Parallel**: 5" in plan_md` AND `assert "**Max Parallel**: 4" not in plan_md` (semantic — verifies exact value)

### 1. `tests/unit/test_batch_planner_overlap.py`

Pure unit tests against `orch.batch_planner.analyze_dependencies`. Use plain `dict` inputs (matching the `items_data` shape the function expects).

Required test cases — each asserts exact membership in `overlap_with` lists:

1. `test_glob_vs_concrete_file_overlap` (AC1)
   - Item A: `impacted_paths=["skills/iw-ai-core-testing/**"]`
   - Item B: `impacted_paths=["skills/iw-ai-core-testing/SKILL.md"]`
   - Assert `"B" in analysis["A"].overlap_with`
   - Assert `"A" in analysis["B"].overlap_with`
   - Assert one of them has the other in `depends_on` (the implicit serialization the planner adds).
2. `test_dir_glob_vs_dir_glob_overlap` (AC1 variant)
   - Item A: `impacted_paths=["a/**"]`
   - Item B: `impacted_paths=["a/b/**"]`
   - Assert overlap detected both ways.
3. `test_strictly_disjoint_paths_no_overlap` (AC4)
   - Item A: `impacted_paths=["foo/bar.py"]`
   - Item B: `impacted_paths=["baz/qux.py"]`
   - Assert `analysis["A"].overlap_with == []`
   - Assert `analysis["B"].overlap_with == []`
4. `test_cross_batch_overlap_uses_globs_intersect` (AC1 cross-batch)
   - Call `analyze_dependencies(items_data, active_items_data=[{...}])` where `active_items_data` has one entry with `impacted_paths=["dashboard/**"]` and the batch's items_data has one entry with `impacted_paths=["dashboard/static/x.js"]`.
   - Assert `analysis[items_data[0]["id"]].cross_batch_conflicts` contains an entry with the active batch's id + item id + the overlap glob list.
5. `test_execution_plan_md_renders_given_max_parallel` (AC3 — value not hardcoded)
   - Call `generate_execution_plan_md(batch_id, analysis, n)` directly for `n` in `(3, 7)`, where `analysis` comes from `analyze_dependencies` on two disjoint items.
   - Assert `f"**Max Parallel**: {n}"` is in the returned markdown for each `n`.
   - This is a GREEN regression-lock (the helper was always correct — the bug was the caller passing literal `4`). It proves the rendered value tracks the argument, which the dashboard test alone cannot show since `create-from-selection` always sets `max_parallel=5`. No RED evidence needed for this case.

Build each test's items_data with the full schema the function expects — read `analyze_dependencies` to see required fields (`id`, `title`, `type`, `impacted_paths`, `steps` (for has_database_step), `depends_on`).

### 2. `tests/dashboard/test_batch_plan_max_parallel.py`

Integration test using `client` (TestClient) from `tests/dashboard/conftest.py` + `db_session` from `tests/conftest.py`.

There is **no** "regenerate-plan" endpoint. The only dashboard path that renders `execution_plan_md` is `POST /project/{project_id}/batch/create-from-selection` (`dashboard/routers/actions.py`, function `create_batch_from_selection`). That endpoint **creates** the Batch — it does not accept a pre-existing one — and constructs it with `max_parallel=5` hardcoded (no `max_parallel` form field). So the dashboard test exercises the create path and asserts the value `5`; the value-variation check lives in the unit test (`test_execution_plan_md_renders_given_max_parallel`, section 1 case 5).

1. `test_create_batch_plan_reads_max_parallel` (AC3)
   - Seed: a Project (slug `p1`) and 2 `WorkItem`s with `status=approved` and NON-overlapping `impacted_paths` (isolates the max_parallel bug from the overlap bug). Do **NOT** pre-create a `Batch` — the endpoint creates it.
   - POST `/project/p1/batch/create-from-selection` with form data `data=[("item_ids", "<id_a>"), ("item_ids", "<id_b>")]` (the endpoint reads `request.form().getlist("item_ids")`).
   - Load the created Batch from the DB session: `db_session.scalars(select(Batch).where(Batch.project_id == "p1")).one()`.
   - Assert `"**Max Parallel**: 5" in batch.execution_plan_md`.
   - Assert `"**Max Parallel**: 4" not in batch.execution_plan_md` (defends against a future regression that re-introduces the literal).

No second dashboard test for `max_parallel=3` — the create endpoint hardcodes `5`, so a different value cannot be produced through the dashboard. Section 1 case 5 covers value variation at the unit level.

### 3. TDD RED evidence

Capture a `tdd_red_evidence` line for each RED-able new test. The RED-able tests are the AC1 glob-overlap unit tests and the `test_create_batch_plan_reads_max_parallel` dashboard test. By the time S03 runs, the S01 fix is already on the branch, so the RED state is **not** reproducible at runtime. Do NOT `git checkout`, `git stash`, or otherwise revert shipped source files to manufacture a RED — that is thrash-prone and is not verification.

Instead, paste the analytic RED line: read the pre-fix code path and state the failure the test *would* have produced. Examples:
- `assert "B" in [] // pre-fix planner.overlap_with empty for glob-vs-concrete-file case (set-equality intersection)`
- `assert "**Max Parallel**: 5" in md → pre-fix md contains "**Max Parallel**: 4" (literal 4 in _build_plan)`

The value-variation unit test (`test_execution_plan_md_renders_given_max_parallel`) is a GREEN regression-lock — no RED evidence required for it.

### 4. Targeted runs only

```bash
uv run pytest tests/unit/test_batch_planner_overlap.py -v
uv run pytest tests/dashboard/test_batch_plan_max_parallel.py -v
```

Do NOT run `make test-unit` or `make test-integration`.

## Project Conventions

- Read `tests/CLAUDE.md`: testcontainers only, NEVER live DB port 5433.
- Tests using `client` fixture MUST be under `tests/dashboard/` (the `client` fixture is registered in `tests/dashboard/conftest.py`).
- Tests using `db_session` are available from both `tests/integration/` and `tests/dashboard/`.

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00104",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_batch_planner_overlap.py",
    "tests/dashboard/test_batch_plan_max_parallel.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "6 passed across 2 files",
  "tdd_red_evidence": "tests/unit/test_batch_planner_overlap.py::test_glob_vs_concrete_file_overlap — AssertionError: assert 'B' in [] (planner.overlap_with empty against pre-fix HEAD per design analysis)",
  "blockers": [],
  "notes": "Dashboard test POSTs to /batch/create-from-selection; value-variation covered by the unit test."
}
```
