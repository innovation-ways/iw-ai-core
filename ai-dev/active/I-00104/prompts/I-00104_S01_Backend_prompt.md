# I-00104_S01_Backend_prompt

**Work Item**: I-00104 -- Batch planner false-negative overlap analysis + Max Parallel display mismatch
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

This step adds **no** migrations. No schema changes.

## Input Files

- `ai-dev/active/I-00104/I-00104_Issue_Design.md`
- `orch/batch_planner.py` (the two overlap loops: ~205-215 intra-batch, ~217-236 cross-batch)
- `orch/daemon/scope_overlap.py` (the `globs_intersect` helper to import)
- `dashboard/routers/actions.py` (lines ~880-900, the `_build_plan` closure)

## Output Files

- `orch/batch_planner.py` — modified
- `dashboard/routers/actions.py` — modified
- `ai-dev/active/I-00104/reports/I-00104_S01_Backend_report.md`

## Context

You are fixing **two related bugs** in a single step (they share a root cause class: planner-vs-runtime disagreement on overlap predicate + plan-render constants).

## Requirements

### 1. Replace plain `set & set` with `globs_intersect` in `orch/batch_planner.py`

**Intra-batch loop (lines ~205-215)**: currently

```python
for i, id_a in enumerate(item_ids):
    for id_b in item_ids[i + 1 :]:
        files_a = set(analysis[id_a].affected_files)
        files_b = set(analysis[id_b].affected_files)
        overlap = files_a & files_b
        if overlap:
            analysis[id_a].overlap_with.append(id_b)
            analysis[id_b].overlap_with.append(id_a)
            if id_a not in analysis[id_b].depends_on:
                analysis[id_b].depends_on.append(id_a)
```

Change to:

```python
from orch.daemon.scope_overlap import globs_intersect  # at top of file with other imports

# ...

for i, id_a in enumerate(item_ids):
    for id_b in item_ids[i + 1 :]:
        files_a = list(analysis[id_a].affected_files)
        files_b = list(analysis[id_b].affected_files)
        overlap = globs_intersect(files_a, files_b)
        if overlap:
            analysis[id_a].overlap_with.append(id_b)
            analysis[id_b].overlap_with.append(id_a)
            if id_a not in analysis[id_b].depends_on:
                analysis[id_b].depends_on.append(id_a)
```

`globs_intersect(a, b)` returns the list of conflicting globs from `a`. Treat any non-empty result as "they overlap" — exactly the existing semantics, but with proper glob handling.

**Cross-batch loop (lines ~217-236)**: same fix — replace `set(analysis[iid].affected_files) & active_files` with `globs_intersect(analysis[iid].affected_files, list(active_files))` and treat non-empty as overlap. Note `active_files` is currently constructed as a set — adapt the call to pass it as a list.

### 2. Fix the `max_parallel=4` hardcode in `dashboard/routers/actions.py`

Around line 890-895, the `_build_plan` closure:

```python
def _build_plan() -> tuple[Any, Any, Any, Any]:
    _analysis = analyze_dependencies(items_data, active_items_data)
    _md = generate_execution_plan_md(batch_id, _analysis, 4)
    _drawio = generate_drawio(batch_id, _analysis, 4)
    _png = generate_png(batch_id, _analysis, 4)
    return _analysis, _md, _drawio, _png
```

Change each literal `4` to `batch.max_parallel`. The surrounding endpoint already has `batch` in scope — verify by reading 30 lines up. If `batch.max_parallel` is not in scope, **STOP and raise a blocker** rather than introduce a side-channel parameter.

### 3. Do NOT touch

- `orch/daemon/scope_overlap.py` (you are importing from it, not modifying it).
- `orch/daemon/batch_manager.py` (runtime path is correct; bug is planner-only).
- Any other dashboard router, any template, any test file (S03 owns tests).
- The Cross-Batch Conflicts rendering in `generate_execution_plan_md` — your fix makes its data correct; no rendering change needed.

## Project Conventions

- Read `orch/CLAUDE.md` for the planner / daemon split.
- `globs_intersect` is pure (no DB, no I/O) — importing it from a planner module that runs at batch-creation time is safe.

## TDD Requirement

Capture **one** RED case in the report (S03 owns the full suite long-term):

1. In a scratch run (do NOT commit a broken test), reproduce AC1 as follows: write a tiny pytest case using `analyze_dependencies` with two items where one declares `skills/iw-ai-core-testing/**` and the other declares `skills/iw-ai-core-testing/SKILL.md`. Assert `"B" in analysis["A"].overlap_with`. Run it against pre-fix HEAD — it MUST fail with `AssertionError: assert 'B' in []`. Paste the failing assertion line into `tdd_red_evidence`. Then implement the fix and re-run — it must pass.

`tdd_red_evidence` example:
```
tests/unit/test_batch_planner_overlap.py::test_glob_vs_concrete_file_overlap —
AssertionError: assert 'B' in [] (analysis["A"].overlap_with is empty — planner missed dir-glob vs file overlap)
```

(S03 will own the long-term test file; your job here is capture the RED evidence.)

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck` (zero errors on touched files)
3. `make lint` (zero errors)

## Test Verification

Run only your one targeted RED-then-GREEN case. Do NOT run `make test-unit` or `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00104",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/batch_planner.py",
    "dashboard/routers/actions.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "1 RED→GREEN case verified manually; full test suite owned by S03 + QV gates",
  "tdd_red_evidence": "tests/unit/test_batch_planner_overlap.py::test_glob_vs_concrete_file_overlap — AssertionError: assert 'B' in [] // captured RED against pre-fix HEAD",
  "blockers": [],
  "notes": "Confirmed batch.max_parallel is in scope at actions.py:892; verified globs_intersect signature accepts list[str]."
}
```
