# I-00083: Branch-base drift across in-flight items — `chore: commit … active files` lands tests without the matching baseline / impl fixes

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-15
**Reported By**: sergio (operator); diagnosed during CR-00053 manual rescue
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. No Docker usage in this fix.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This fix leaves migrations unchanged.)

## Description

When two work items are in flight concurrently, item B's worktree can
end up containing tests whose matching implementation has not yet
merged. Two distinct sub-causes are addressed by this incident:

1. **Chore-commit leak**: `chore: commit <A> active files before approval`
   lands at approval time and currently ships *everything* under
   `ai-dev/active/<A>/`. If any test fixtures, scripts, or helpers were
   placed there pre-approval, they reach `main` without the matching
   impl. Items branched after that chore commit but before A merges see
   half-state.
2. **Cross-item out-of-scope test writes**: an already-merging item F
   may have written test files outside its own `ai-dev/active/<F>/` dir
   that exercise behavior *another* still-in-flight item C is producing.
   F's squash merge lands those tests on `main` legitimately, but C's
   matching impl has not merged. Item B, branched after F but before C,
   inherits the broken state — and B's QV gates fail on tests that
   target C's pending impl, not B's quality. (This is the CR-00053 bite.)

The fix addresses both: (1) narrow the chore commit, and (2) at
worktree-create time, detect when B's base contains files matching an
in-flight sibling's `allowed_paths` *without* the sibling's merge commit
yet, and surface that drift in the daemon log.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard
rules. Most relevant: `orch/cli/item_commands.py` (the `iw approve`
command writes the chore commit), `orch/daemon/batch_manager.py` (the
worktree-creation path), `executor/setup_worktree.sh` (the actual
`git worktree add`).

## Steps to Reproduce

1. Approve item A; observe `chore: commit <A> active files before approval`
   on `main` containing only `ai-dev/active/<A>/...`.
2. Item A executes; during its work it updates an assertion baseline file
   (`tests/assertion_free_baseline.txt`) or a test-expectation constant
   (e.g., `BatchStatus.executing` → `BatchStatus.completed`) to keep gates
   green. These edits land in A's worktree only.
3. **Without waiting for A to merge**, approve item B and let the daemon
   create B's worktree. B is branched from the current `main` — which
   includes A's chore commit and any A-related test files that came in
   via that commit.
4. B runs QV gates. A's test files are present in B's worktree but
   A's baseline / impl fixes are not. Gates fail on A's tests.

**Expected**: B's worktree should either (a) not inherit A's test files
at all (only true `main` content), or (b) inherit A's complete in-flight
state including baseline / impl fixes. Either is consistent.

**Actual**: B inherits A's tests in their broken pre-A-implementation
state. The fix-cycle agent then thrashes trying to "fix" A's tests from
inside B's worktree (see I-00082 for the second-order pain).

## Root Cause Analysis

The `chore: commit <X> active files before approval` step (driven from
`orch/cli/item_commands.py::approve` and the surrounding logic) commits
the entire `ai-dev/active/<X>/` directory. For most items this is just
the design doc, prompts, and manifest — but if the user (or any agent)
has placed test fixtures, scripts, or other non-design files under
`ai-dev/active/<X>/` BEFORE approval, those land on main too.

The actual bite seen on CR-00053 was different: CR-00052's chore commit
landed at `596c3084` on 2026-05-14 21:55. Concretely, this only added
`ai-dev/active/CR-00052/` files. But CR-00052's tests
(`tests/dashboard/test_cancel_*.py`, additions to
`tests/assertion_free_baseline.txt`) had been WRITTEN OUTSIDE the active
directory by a previous in-flight item (F-00082). When F-00082 merged at
`83cbf086`, those test files landed on main as part of the squash merge.
CR-00053's worktree, branched after both, inherited F-00082's tests +
CR-00052's chore commit + CR-00053's chore commit but NOT CR-00052's
implementation (which made `executing` cancellable and updated the
matching test).

Two sub-causes are tangled here:

1. **Squash merges land tests + impl atomically** (good). But
   `chore: commit ... active files before approval` is a separate commit
   that ONLY ships ai-dev/ files. Items branched between the chore commit
   and the squash-merge commit see partial state.
2. **No cross-item awareness** — when B is branched, the daemon does not
   check whether any item A is mid-flight whose pending impl would
   conflict with B's gates.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/cli/item_commands.py` (`approve`) | Writes the chore commit; could narrow scope or defer |
| `orch/daemon/batch_manager.py` | Worktree creation; could rebase pending impl into the worktree |
| `executor/setup_worktree.sh` | Actual `git worktree add`; same place a fix could insert |
| `executor/worktree_commit.sh` | Already does pre-merge rebase (CR-00021) — could mirror that on creation |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Pipeline | Implement two complementary changes: **(b)** narrow `iw approve` chore commit to design/manifest/prompts only, AND **launch-time sibling-scope check** in `batch_manager.py` that — at worktree-create time — computes `sibling_paths_without_merge` and emits an INFO log line. Write the minimal AC1 RED reproduction test as part of TDD. | — |
| S02 | CodeReview | Per-agent review of S01 | — |
| S03 | Tests | Extend `tests/integration/test_branch_base_drift.py` (the file S01 created with the AC1 reproduction) with the AC3 happy-path regression, the sibling-scope-check unit tests, and reusable fake-repo helpers. | — |
| S04 | CodeReview | Per-agent review of S03 | — |
| S05 | CodeReview_Final | Cross-agent global review | — |
| S06..S13 | QV Gates | lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S14 | SelfAssess | Self-assessment via iw-item-analyze skill | — |

### Implementation options (DECIDED)

Three options were considered:

- **(a) Stop pre-committing `ai-dev/active/<ID>/` at approval time** —
  rejected; breaks the dashboard's "preview design before run" feature.
- **(b) Pre-commit only the design docs / manifest / prompts** under
  `ai-dev/active/<ID>/`. Anything else (test fixtures, scripts,
  evidences) stays untracked at approval time and travels with the
  squash merge instead.
- **(c) On worktree create, stack pending in-flight items' impl as soft
  rebases** — rejected; operationally complex (which items? what order?
  what about conflicts?).

**Decision**: **(b) + launch-time sibling-scope check** (i.e., a hybrid
that addresses both sub-causes without (c)'s complexity).

- (b) eliminates the chore-commit leak class of bugs.
- The launch-time check addresses the cross-item out-of-scope test-write
  class (the actual CR-00053 bite). At worktree-create, the daemon
  computes `sibling_paths_without_merge` — paths present in B's base
  that match an in-flight sibling's `allowed_paths` but where the
  sibling has not yet merged — and emits the count + sibling list in an
  INFO line. **WARN, not BLOCK**, for v1: operators can escalate later.

### Database Changes

- **New tables**: None.
- **Modified tables**: None.
- **Migration notes**: No schema impact.

### Code Changes

- **`orch/cli/item_commands.py`** — narrow the chore commit's file set
  to `<ID>_*_Design.md`, `<ID>_Functional.md`, `workflow-manifest.json`,
  `prompts/**`. Add a commented allow-list naming the exclusion and
  citing I-00083.
- **`orch/daemon/batch_manager.py`** — at worktree-create, query
  `WorkItem`s in `approved` / `executing` / `merging` for the same
  project; for each in-flight sibling, intersect its `allowed_paths`
  with files actually present in B's base tree; emit one INFO log line
  (see S01 prompt for shape). No blocking behavior in v1.
- **`executor/setup_worktree.sh`** — touched only if the log emission
  needs a hand-off; preferably left untouched.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00083_Issue_Design.md` | Design | This document |
| `I-00083_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00083_S01_Pipeline_prompt.md` | Prompt | S01 fix |
| `prompts/I-00083_S02_CodeReview_Pipeline_prompt.md` | Prompt | S02 review |
| `prompts/I-00083_S03_Tests_prompt.md` | Prompt | S03 tests |
| `prompts/I-00083_S04_CodeReview_Tests_prompt.md` | Prompt | S04 test review |
| `prompts/I-00083_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00083_S14_SelfAssess_prompt.md` | Prompt | S14 self-assess |

## Test to Reproduce

```python
def test_i00083_b_worktree_does_not_inherit_a_pre_impl_test_drift(tmp_path, monkeypatch):
    """Worktree for item B, created while item A is in flight, must not
    fail QV gates on test files A added before A's impl landed.

    This test should FAIL before the fix and PASS after.
    """
    # Arrange — fake repo with a "main" branch
    repo = make_fake_repo(tmp_path)
    # Simulate item A's chore commit + A's in-progress (un-merged) impl
    a_chore_sha = simulate_chore_commit(repo, item_id="A-99001")
    simulate_in_flight_impl(repo, item_id="A-99001", touches=["tests/test_drift.py"])
    # Item B is approved while A is still in-flight
    simulate_chore_commit(repo, item_id="B-99002")

    # Act — create B's worktree
    b_worktree = create_worktree(repo, item_id="B-99002")

    # Assert — B's worktree does NOT contain A's tests/test_drift.py
    # (option b/c) OR contains a synced copy that matches A's pending impl
    # (option c). Either way, the file's presence-without-impl is a bug.
    assert not (b_worktree / "tests" / "test_drift.py").exists() or \
           is_test_fully_runnable(b_worktree / "tests" / "test_drift.py"), (
        "B's worktree inherited A's tests but not A's matching impl — drift bug"
    )
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given item A is in-flight and has un-merged test/impl edits
When item B is approved and its worktree is created
Then B's worktree does not include A's test files in their pre-impl broken state
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/integration/test_branch_base_drift.py passes
```

### AC3: Single-item happy path is preserved

```
Given only one item is in flight
When the worktree is created
Then no behavioural change vs today (the chore commit / worktree creation continues to work)
```

## Regression Prevention

- AC1 reproduction test (authored at S01, kept at S03) pins the
  no-drift behaviour for the chore-commit path.
- AC3 happy-path test (authored at S03) pins the solo-item flow's
  byte-equivalence and the `sibling_paths_without_merge=0` log shape.
- Daemon INFO log at worktree-create time emits
  `in_flight_siblings=[…] sibling_paths_without_merge=<N> details=[…]`;
  any non-zero `N` is an operator-visible warning that a future
  carry-over is being set up.
- Operator-readable allow-list comment in `orch/cli/item_commands.py`
  near the chore-commit logic names exactly what is excluded and cites
  I-00083 to deter "fix-it-by-re-adding" regressions.

## Dependencies

- **Depends on**: None.
- **Blocks**: I-00082 effectiveness (drift across in-flight items is
  one of the main reasons fix-cycle agents need to make out-of-scope
  edits in the first place; fixing both eliminates a recurring class
  of stuck CRs).

## Impacted Paths

- `orch/cli/item_commands.py`
- `orch/daemon/batch_manager.py`
- `executor/setup_worktree.sh`
- `tests/integration/test_branch_base_drift.py`

## TDD Approach

- Reproducing test: as above.
- Unit tests: helper functions for "list in-flight sibling items at this
  SHA", "compute path-set to exclude from chore commit".
- Integration tests: end-to-end fake-repo simulation with two in-flight
  items.

## Notes

This is the structural cause of the carry-over fixes that operators have
been applying by hand. Concrete carry-overs from CR-00053:

- 5 entries appended to `tests/assertion_free_baseline.txt` (CR-00052
  carry-over)
- 1-line `BatchStatus.executing` → `BatchStatus.completed` in
  `tests/integration/test_dashboard_actions.py` (CR-00052 carry-over)

Both edits were correct and harmless individually, but each one was
out-of-scope for CR-00053 and triggered the fix-cycle thrashing
documented in I-00082.

This incident is filed Medium severity rather than High because:

- It is recoverable with operator carry-over fixes.
- It only manifests when 2+ items are concurrently in flight (single-item
  flow is unaffected).
- Fixing I-00082 reduces the cost of each occurrence dramatically even
  before this incident is fixed.
