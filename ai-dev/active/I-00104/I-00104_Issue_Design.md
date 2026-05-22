# I-00104: Batch planner false-negative overlap analysis + Max Parallel display mismatch

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-22
**Reported By**: sergio (live observation on BATCH-00127)
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This Incident adds **no** schema changes and **no** Alembic migrations. The fix is pure logic in `orch/batch_planner.py` and a one-line correction in `dashboard/routers/actions.py`.

## Description

The batch Plan tab and the runtime overlap-gate disagree. The Plan tab's Dependency Analysis declares every item independent and the Warnings section literally says "None — all items are independent." But the daemon's runtime overlap-lock correctly holds 5 of the 7 items in BATCH-00127 due to shared file globs. Additionally, the same Plan tab markdown displays `Max Parallel: 4` while the page header chip and the `<select>` element both show `5` (the actual `Batch.max_parallel`). The first bug actively misleads operators; the second erodes trust.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. This Incident is confined to the orchestration planner module (`orch/batch_planner.py`), the dashboard batch-create endpoint `POST /batch/create-from-selection` (`dashboard/routers/actions.py`), and the existing pure overlap helper (`orch/daemon/scope_overlap.py`) that the planner must start using.

## Browser Evidence

- `ai-dev/active/I-00104/evidences/pre/I-00104-plan-tab-says-no-overlap.png` — Plan tab of BATCH-00127 showing the Dependency Analysis table with `Overlap With: None` for every row, the "Group 0 (parallel)" listing of all 7 items, the Warnings section saying "None — all items are independent", AND the summary line `**Max Parallel**: 4`.
- `ai-dev/active/I-00104/evidences/pre/I-00104-items-tab-five-held.png` — Items tab of the same BATCH-00127 showing 5 items with `Held: overlaps with CR-00076 on docs/IW_AI_Core_Testing_Strategy.md, skills/iw-ai-core-testing/**+2` pills, AND the page header showing `Max parallel: 5`.

The contradiction between the two tabs of the same batch is the bug.

## Steps to Reproduce

### Bug 1: False-negative overlap analysis

1. Create two work items where one has a glob-style `impacted_paths` entry (e.g. `skills/iw-ai-core-testing/**`) and the other has a concrete file under that directory (e.g. `skills/iw-ai-core-testing/SKILL.md`).
2. Approve both, then `iw batch-create <id1> <id2>`.
3. Open the batch detail page → Plan tab.

**Expected**: The Dependency Analysis table shows both items in each other's "Overlap With" column. The Warnings section flags the file overlap. The two items are placed in serial groups OR explicitly warned about. The runtime overlap-gate at execution time agrees with the plan.

**Actual**: The Dependency Analysis shows `Overlap With: None` for both. The Warnings section says "None — all items are independent." Both items are placed in Group 0 parallel. At runtime, whichever item starts first holds the lock; the second is Held by the daemon.

### Bug 2: Max Parallel display mismatch

1. Create a batch with `max_parallel = 5` (or any value other than 4).
2. Open the batch detail page → Plan tab.

**Expected**: The plan markdown's `**Max Parallel**: N` matches both the page header chip and the `<select>` element's selected value, all read from `Batch.max_parallel`.

**Actual**: The markdown always says `**Max Parallel**: 4` regardless of the actual `Batch.max_parallel`. The header and select correctly show the DB value.

## Browser Verification Script

```bash
# Reproduce the plan-tab evidence
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
# Navigate via UI to a batch with at least 2 items whose impacted_paths
# share a glob (BATCH-00127 in seed is the canonical example).
# Then: ?tab=plan
playwright-cli screenshot
# Compare the markdown summary line vs the header chip — they must match
# after the fix.
```

## Root Cause Analysis

### Bug 1 — `orch/batch_planner.py:208-213`

```python
# Phase 3: File overlap detection (intra-batch)
for i, id_a in enumerate(item_ids):
    for id_b in item_ids[i + 1 :]:
        files_a = set(analysis[id_a].affected_files)
        files_b = set(analysis[id_b].affected_files)
        overlap = files_a & files_b           # ← plain set intersection
        if overlap:
            analysis[id_a].overlap_with.append(id_b)
            analysis[id_b].overlap_with.append(id_a)
            ...
```

Plain `set & set` is **exact string-equality** matching. So `skills/iw-ai-core-testing/**` does not collide with `skills/iw-ai-core-testing/SKILL.md` — the planner declares them independent.

The runtime path in `orch/daemon/batch_manager.py:457` uses `scope_overlap.find_blocking_items(...)` which internally calls `scope_overlap.globs_intersect(a, b)` — **fnmatch + anchor-containment**, the correct semantics for gitignore-style globs. So `skills/iw-ai-core-testing/**` correctly intersects `skills/iw-ai-core-testing/SKILL.md` at runtime.

**Fix**: replace the plain set intersection with `scope_overlap.globs_intersect(files_a_list, files_b_list)` (preserving list order on the input side — the helper expects lists, not sets). The result is the list of conflicting globs; non-empty result means the two items overlap.

### Bug 2 — `dashboard/routers/actions.py:892-894`

```python
def _build_plan() -> tuple[Any, Any, Any, Any]:
    _analysis = analyze_dependencies(items_data, active_items_data)
    _md = generate_execution_plan_md(batch_id, _analysis, 4)      # ← literal 4
    _drawio = generate_drawio(batch_id, _analysis, 4)             # ← literal 4
    _png = generate_png(batch_id, _analysis, 4)                   # ← literal 4
    return _analysis, _md, _drawio, _png
```

The three planner-render calls pass a literal `4` instead of `batch.max_parallel`. `_build_plan` is a closure inside the `POST /batch/create-from-selection` endpoint, which constructs the `Batch` row a few lines earlier with `max_parallel=5` hardcoded (the endpoint exposes no `max_parallel` form field). So `batch` — and `batch.max_parallel` — is already in scope. The header chip and `<select>` read `Batch.max_parallel` (5); the plan markdown reads the literal `4`; hence the mismatch. The CLI counterpart in `orch/cli/batch_commands.py:_generate_batch_plan` passes `batch.max_parallel`, which is why CLI-created batches show consistent numbers but dashboard-created plans always say 4.

There is **no** separate "regenerate-plan" endpoint — `_build_plan` runs exactly once, at batch creation. `POST /batch/{id}/max-parallel` updates the column only; it does not re-render `execution_plan_md`.

**Fix**: replace each `4` with `batch.max_parallel`.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/batch_planner.py` (intra-batch overlap loop, lines 208-213) | Misses every glob-vs-concrete-file overlap → operator sees "all independent" |
| `orch/batch_planner.py` (cross-batch overlap loop, lines 217-236) | Same string-equality bug; same fix (use `globs_intersect`) |
| `dashboard/routers/actions.py:892-894` | Plan markdown / drawio / PNG always rendered with `max_parallel=4` |
| `dashboard/templates/pages/project/batch_detail.html` (Plan tab) | Displays the wrong number from the markdown source |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Replace `set & set` with `scope_overlap.globs_intersect(...)` in intra-batch loop AND cross-batch loop in `orch/batch_planner.py`. Replace the three literal `4`s in `dashboard/routers/actions.py:892-894` with `batch.max_parallel`. | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | tests-impl | (a) Unit tests in `tests/unit/test_batch_planner_overlap.py` exercising the fnmatch / anchor-containment semantics inside the planner: glob-vs-concrete-file, dir-glob-vs-dir-glob, no-overlap negative, cross-batch; plus a value-variation test on `generate_execution_plan_md` (max_parallel 3/7); (b) Dashboard test that the batch-create endpoint (`create-from-selection`) produces plan markdown with `**Max Parallel**: 5` (the value it hardcodes). RED evidence captured for the RED-able tests. | — |
| S04 | code-review-impl | Per-agent review of S03 | — |
| S05 | code-review-final-impl | Global cross-agent review | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `make format-check` | — |
| S08 | qv-gate | `make type-check` | — |
| S09 | qv-gate | `make test-unit` | — |
| S10 | qv-gate | `make test-integration` | — |
| S11 | qv-gate | `make test-assertions` | — |
| S12 | qv-browser | Playwright: open the Plan tab of a batch with overlapping items; assert the Plan tab Dependency Analysis shows overlap pairs; assert `Max Parallel: N` matches header `Max parallel: N` | — |
| S13 | self-assess-impl | Post-execution analysis via iw-item-analyze | — |

### Database Changes

- **New tables**: None.
- **Modified tables**: None.
- **Migration notes**: No alembic migration in this fix.

### Code Changes

- **Files to modify**:
  - `orch/batch_planner.py` (replace plain set intersection in both overlap loops; import `globs_intersect` from `orch.daemon.scope_overlap`).
  - `dashboard/routers/actions.py` (line 892-894 literal `4` → `batch.max_parallel`).
- **Nature of change**: Logic correction. No new endpoints, no new functions, no schema change.

## File Manifest

All files for this work item live under `ai-dev/active/I-00104/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00104_Issue_Design.md` | Design | This document |
| `I-00104_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00104_S01_Backend_prompt.md` | Prompt | S01 fix |
| `prompts/I-00104_S02_CodeReview_prompt.md` | Prompt | S02 review |
| `prompts/I-00104_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00104_S04_CodeReview_prompt.md` | Prompt | S04 review |
| `prompts/I-00104_S05_CodeReview_Final_prompt.md` | Prompt | S05 cross-agent review |
| `prompts/I-00104_S12_BrowserVerification_prompt.md` | Prompt | S12 Playwright |
| `prompts/I-00104_S13_SelfAssess_prompt.md` | Prompt | S13 analysis |
| `evidences/pre/I-00104-plan-tab-says-no-overlap.png` | Evidence | Plan tab BEFORE fix |
| `evidences/pre/I-00104-items-tab-five-held.png` | Evidence | Items tab showing the 5 Held items the planner missed |

## Test to Reproduce

```python
# tests/unit/test_batch_planner_overlap.py

from orch.batch_planner import analyze_dependencies


def test_i00104_planner_detects_glob_vs_concrete_file_overlap():
    """Two items where one declares dir/** and the other a concrete file under
    dir/ MUST be flagged as overlapping. Before the fix, this test FAILS
    because the planner uses plain set intersection (string equality)."""
    items = [
        {
            "id": "A",
            "title": "A",
            "type": "ChangeRequest",
            "impacted_paths": ["skills/iw-ai-core-testing/**"],
            "steps": [],
            "depends_on": [],
        },
        {
            "id": "B",
            "title": "B",
            "type": "ChangeRequest",
            "impacted_paths": ["skills/iw-ai-core-testing/SKILL.md"],
            "steps": [],
            "depends_on": [],
        },
    ]
    analysis = analyze_dependencies(items, active_items_data=None)
    assert "B" in analysis["A"].overlap_with
    assert "A" in analysis["B"].overlap_with
```

```python
# tests/dashboard/test_batch_plan_max_parallel.py

def test_i00104_create_batch_plan_reads_max_parallel(client, db_session):
    """The batch-create endpoint must render the plan markdown with the
    created Batch.max_parallel value (5), not the literal 4. Before the fix
    the markdown always reads "**Max Parallel**: 4"."""
    # Seed a Project + two approved WorkItems with non-overlapping impacted_paths.
    # POST create-from-selection with item_ids form fields — the endpoint
    # CREATES the Batch (max_parallel=5 hardcoded) and renders the plan.
    response = client.post(
        f"/project/{slug}/batch/create-from-selection",
        data=[("item_ids", id_a), ("item_ids", id_b)],
    )
    batch = db_session.scalars(
        select(Batch).where(Batch.project_id == slug)
    ).one()
    assert "**Max Parallel**: 5" in batch.execution_plan_md
    assert "**Max Parallel**: 4" not in batch.execution_plan_md
```

```python
# tests/unit/test_batch_planner_overlap.py — value-variation unit test

def test_i00104_execution_plan_md_renders_given_max_parallel():
    """generate_execution_plan_md must render whatever max_parallel it is
    given — proves the value is not re-hardcoded to 5 either. The dashboard
    test alone cannot show this, since create-from-selection always sets 5."""
    from orch.batch_planner import analyze_dependencies, generate_execution_plan_md
    analysis = analyze_dependencies([_disjoint_a, _disjoint_b], None)
    for n in (3, 7):
        md = generate_execution_plan_md("BATCH-TEST", analysis, n)
        assert f"**Max Parallel**: {n}" in md
```

The batch-create dashboard test (and the AC1 glob-overlap unit tests) must
FAIL before the fix and PASS after. The value-variation unit test on
`generate_execution_plan_md` passes both before and after — that helper was
always correct; the bug was the *caller* passing a literal `4`. Its role is to
regression-lock the rendered value so a future refactor cannot re-hardcode it.

## Browser Verification Test

In `prompts/I-00104_S12_BrowserVerification_prompt.md`:

1. Navigate to a batch detail Plan tab where at least two items share overlapping globs.
2. Assert the Dependency Analysis table has at least one row with a non-empty `Overlap With` column.
3. Assert the Warnings section is NOT the literal "None — all items are independent." when overlaps exist.
4. Read the page header `Max parallel: N` (where N is the actual `Batch.max_parallel`).
5. Assert the rendered plan markdown contains `Max Parallel: N` (same N).

## Acceptance Criteria

### AC1: Overlap detection uses fnmatch semantics

```
Given two items where one declares `dashboard/**` and the other declares `dashboard/static/foo.js`
When analyze_dependencies runs
Then both items list each other in `overlap_with`
And the Plan tab Warnings section lists this overlap
And the runtime overlap-gate's hold pattern is consistent with the plan's prediction
```

### AC2: Reproduction tests exist and pass

```
Given the fix is applied
When test_i00104_planner_detects_glob_vs_concrete_file_overlap runs against the fix
Then it passes
And the same test against pre-fix HEAD (verified at design time, not by the agent at runtime) fails
```

### AC3: Plan markdown max_parallel matches the batch

```
Given a batch created via POST /batch/create-from-selection (max_parallel=5)
When the execution plan markdown is generated
Then execution_plan_md contains "**Max Parallel**: 5"
And does NOT contain "**Max Parallel**: 4"
```

```
Given generate_execution_plan_md is called directly with max_parallel=N
When the markdown is rendered
Then it contains "**Max Parallel**: N" (verified for N=3 and N=7 — value not hardcoded)
```

### AC4: No regression on no-overlap path

```
Given two items with strictly disjoint impacted_paths (no string overlap, no glob containment)
When analyze_dependencies runs
Then their overlap_with lists are empty
And both end up in Group 0 (parallel)
```

### AC5: No regression on existing tests

```
Given all pre-existing planner and dashboard tests
When the full test suite runs after the fix
Then no test fails (no incidental regression)
```

## Regression Prevention

- **Shared helper**: the fix replaces the duplicate string-equality logic with a single call to `scope_overlap.globs_intersect`. The planner and the runtime now share the same overlap predicate. Future planner changes that introduce a divergent overlap implementation are caught by the new tests.
- **Test coverage**: AC1 + AC3 reproduction tests anchor both regressions. Specifically the AC1 test is a class-of-bug guard — any future regression that replaces `globs_intersect` with a string match will fail this test.
- **Constant-vs-DB-value lint**: the `max_parallel=4` literal was hidden in a helper closure inside a router. A future refactor that introduces another `generate_execution_plan_md(...)` call site MUST pass `batch.max_parallel`. The dashboard test in S03 covers the batch-create path, and the unit value-variation test covers `generate_execution_plan_md` directly; if a new call site appears, a test should be added there too (note this as a follow-up reminder, not a separate work item).

## Dependencies

- **Depends on**: None.
- **Blocks**: None — but the user-visible effects of CR-00077 (the popup) become more useful once the planner agrees with the runtime: the popup will less often surprise the operator with overlaps the plan didn't mention.

## Impacted Paths

- `orch/batch_planner.py`
- `dashboard/routers/actions.py`
- `tests/unit/test_batch_planner_overlap.py`
- `tests/dashboard/test_batch_plan_max_parallel.py`

## TDD Approach

- **Reproducing tests**: the two test files above. Both fail before the fix, pass after.
- **Unit tests**: planner overlap detection — at minimum the glob-vs-concrete-file case, and a no-overlap negative case to confirm AC4.
- **Integration tests**: the dashboard batch-create flow — see `tests/dashboard/test_batch_plan_max_parallel.py`. Uses `db_session` testcontainer + TestClient; POSTs to `create-from-selection`, then reads the resulting `Batch.execution_plan_md` from the DB and asserts exact substrings.

**Assertion scoping for CSS class names** is N/A here — no CSS assertions. The tests assert exact markdown substrings (`**Max Parallel**: N`) and exact membership in `analysis[...].overlap_with` lists.

## Notes

- The same `set & set` pattern also lives in the cross-batch overlap loop (`orch/batch_planner.py:217-236`). S01 must fix both loops in the same step — they share the same conceptual bug.
- `scope_overlap.globs_intersect` is already pure (no DB, no I/O), so importing it into `orch/batch_planner.py` is safe and respects the planner's pure-function character.
- The planner uses `analysis[iid].affected_files` which is a `list[str]` (not a set). `globs_intersect` expects lists — no conversion needed.
- The planner does NOT currently apply the per-project `overlap_block_patterns` / `overlap_allow_patterns` policy. The runtime does. Aligning policy is **out of scope** for this Incident — the planner showing "they overlap" when runtime would still hold them is correct enough for operator-facing UX. A future enhancement may pass the policy in too; if so, file a CR.
- **Per-batch isolation note**: BATCH-00127 will continue to execute correctly while this Incident is in flight. The fix only affects the Plan tab display and the planner's `overlap_with` field — the runtime overlap-gate is already doing the right thing.
