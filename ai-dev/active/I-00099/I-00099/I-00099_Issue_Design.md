# I-00099: Scope-overlap sibling-dir rule generates false-positive cross-batch holds

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-18
**Reported By**: sergio (observed while unblocking CR-00060 against in-flight CR-00057)
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item leaves migrations unchanged. No schema changes; the fix is to a pure-Python module in `orch/daemon/`.

## Description

The cross-batch scope-overlap gate (F-00076) holds work items that share **only a parent directory** with an in-flight item, even when the actual files are different and don't conflict. The hold is logged as `Held: X overlaps with Y on <file>` which misleadingly names a specific file as the conflict when the real trigger is the structural sibling-directory heuristic. Operators have to manually edit `impacted_paths` (DB + design doc + manifest) every time the daemon trips this rule against an unrelated item.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The cross-batch conflict gate is described in `orch/CLAUDE.md` (batch_manager) and was introduced by F-00076; the merge-time mirror lives in `executor/scope_gate.py` (off-by-default at the project level for `iw-ai-core`).

## Steps to Reproduce

1. Register two items in different batches. Item A's `impacted_paths` includes `docs/A.md`; item B's includes `docs/B.md` (different filenames; no glob overlap).
2. Approve and launch item A; wait until it reaches `in_progress` (worktree created, step running).
3. Approve item B in a second batch and let the daemon poll (~60 s).
4. Observe `daemon_events` row of type `item_held_for_scope`: `Held: B overlaps with A on docs/B.md`.

**Expected**: Item B launches normally. Neither item writes the same file; the two paths share only their parent directory; that is not a real conflict.

**Actual**: Item B is held in `pending` indefinitely until either A finishes or an operator manually edits `WorkItem.impacted_paths` to remove the offending sibling path.

Concrete live example (2026-05-18):

- `daemon_events`: `Held: CR-00060 overlaps with CR-00057 on docs/IW_AI_Core_Testing_Strategy.md`. CR-00057 declares `docs/IW_AI_Core_AI_Assistant_Models.md`. Distinct files, same parent.
- After removing that doc from CR-00060's scope, a second sibling overlap surfaced: `orch/daemon/batch_manager.py` (CR-00060, optional) ↔ `orch/daemon/project_registry.py` (CR-00057). Distinct files, same parent.

## Root Cause Analysis

`orch/daemon/scope_overlap.py::find_blocking_items` (lines 135–172) computes `globs_intersect()` first; when it returns empty, it falls back to a structural sibling-directory check:

```python
# orch/daemon/scope_overlap.py:160-168
if not intersecting:
    for cp in candidate_paths:
        for ifp in in_flight_paths:
            if _same_parent(cp, ifp):
                intersecting = [cp]
                break
        if intersecting:
            break
```

`_same_parent()` at lines 128–132 is purely structural: it splits each path on the last `/` and compares the resulting parents byte-for-byte. There is no notion of module size, fanout, or coupling. The function fires for any two files sharing a parent directory, regardless of whether the directory is a tight 3-file package or a loose `docs/` folder with dozens of independent files.

The rule's original intent was to guard against two parallel agents touching the same Python package, but it was never narrowed to small/tight directories. As more items declare paths in shared `docs/`, `orch/daemon/`, `orch/cli/`, `dashboard/routers/`, etc., false-positive holds scale with batch concurrency.

Additionally, the event-emission site in `orch/daemon/batch_manager.py:408-410` calls `', '.join(conflicting_globs[:3])` where `conflicting_globs` is set to `[cp]` (the candidate path) in the sibling case — so the message names a specific file as "the conflict" when the real trigger is "you both happen to write something under the same dir". This makes the message misleading and explains why the user's diagnostic took a layer of investigation before the structural cause became visible.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/scope_overlap.py` | `find_blocking_items` returns false positives; `_same_parent` is the bug. |
| `orch/daemon/batch_manager.py` (caller, NOT modified) | Holds items based on the false positives; emits misleading `item_held_for_scope` event. |
| `tests/unit/daemon/test_scope_overlap.py` | Has a test (`test_non_test_sibling_still_blocks`) that asserts the buggy behaviour we are removing. Must be deleted. The `TestI00071RegressionBatch00078` class remains relevant (test-path stripping) but its docstrings reference the sibling rule and need refreshing. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Remove `_same_parent` and the sibling fallback from `find_blocking_items` in `orch/daemon/scope_overlap.py`. Refresh the module docstring with a note recording the I-00099 removal and rationale. No change to `globs_intersect` or `_strip_test_globs`. | — |
| S02 | CodeReview | Review S01 | — |
| S03 | Tests | Reproduction test (the two real CR-00057↔CR-00060 pairs MUST NOT block); delete `test_non_test_sibling_still_blocks` (asserts the buggy behaviour); refresh `TestI00071RegressionBatch00078` docstrings; positive regression tests: exact-file match still blocks, `orch/daemon/**` glob still blocks any file under that anchor. | — |
| S04 | CodeReview | Review S03 (tests) | — |
| S05 | CodeReview_Final | Global cross-agent review | — |
| S06..S10 | QV Gates | lint, format-check, type-check, unit-tests, integration-tests | — |
| S11 | SelfAssess | Self-assessment via iw-item-analyze | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — pure Python module change.

### Code Changes

- **Files to modify**:
  - `orch/daemon/scope_overlap.py` (Backend, S01)
  - `tests/unit/daemon/test_scope_overlap.py` (Tests, S03)
- **Nature of change**: Remove the sibling-directory fallback. Keep `globs_intersect` and `_strip_test_globs` intact. Delete dead helper `_same_parent` and the obsolete unit test that pinned the wrong behaviour.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00099_Issue_Design.md` | Design | This document |
| `I-00099_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00099_S01_Backend_prompt.md` | Prompt | S01 Backend — remove sibling rule |
| `prompts/I-00099_S02_CodeReview_Backend_prompt.md` | Prompt | S02 per-agent review of S01 |
| `prompts/I-00099_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00099_S04_CodeReview_Tests_prompt.md` | Prompt | S04 per-agent review of S03 |
| `prompts/I-00099_S05_CodeReview_Final_prompt.md` | Prompt | S05 final cross-agent review |
| `prompts/I-00099_S11_SelfAssess_prompt.md` | Prompt | S11 self-assessment |

## Test to Reproduce

The reproduction test goes in `tests/unit/daemon/test_scope_overlap.py` because the bug is in a pure Python module with no DB or fixture requirements. The Tests step writes the test exactly as below; it FAILS against pre-S01 code (the sibling rule fires) and PASSES after S01 removes the rule.

```python
class TestI00099SiblingDirNoLongerBlocks:
    """I-00099 regression — sibling-directory false-positive holds.

    Two items that each touch a *different* file in a shared parent directory
    must not block each other. The pre-fix code's `_same_parent` fallback
    fired for any two files sharing a parent dir; this is now removed.
    Items that genuinely need module-level exclusion must declare an
    explicit glob (`dir/**`) or the exact same file.
    """

    def test_two_different_docs_in_same_dir_do_not_block(self) -> None:
        """Real CR-00057↔CR-00060 case: docs/A.md and docs/B.md must not block."""
        candidate_paths = ["docs/IW_AI_Core_Testing_Strategy.md"]
        in_flight = [
            ("CR-00057", ["docs/IW_AI_Core_AI_Assistant_Models.md"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        assert result == [], (
            "Two items declaring different files under docs/ must not block "
            f"each other via the sibling-directory heuristic. Was: {result!r}"
        )

    def test_two_different_daemon_modules_do_not_block(self) -> None:
        """Real CR-00057↔CR-00060 case: orch/daemon/A.py and orch/daemon/B.py must not block."""
        candidate_paths = ["orch/daemon/batch_manager.py"]
        in_flight = [
            ("CR-00057", ["orch/daemon/project_registry.py"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        assert result == [], (
            "Two items declaring different files under orch/daemon/ must not "
            f"block each other via the sibling-directory heuristic. Was: {result!r}"
        )
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given two work items in different batches, item A and item B
And item A is in_progress with impacted_paths = ["docs/IW_AI_Core_AI_Assistant_Models.md"]
And item B is approved with impacted_paths = ["docs/IW_AI_Core_Testing_Strategy.md"]
When the daemon's launch-time scope-overlap gate evaluates item B
Then find_blocking_items returns [] (no block)
And the daemon launches item B normally without emitting item_held_for_scope
```

### AC2: Regression test exists

```
Given the fix is applied to orch/daemon/scope_overlap.py
When `make test-unit` runs
Then tests/unit/daemon/test_scope_overlap.py::TestI00099SiblingDirNoLongerBlocks passes
And the obsolete test_non_test_sibling_still_blocks no longer exists
And both real-world CR-00057↔CR-00060 reproductions are codified as regression cases
```

### AC3: Exact-file and glob-anchor overlaps still block

```
Given the fix is applied
When two items declare the exact same path (e.g., both "dashboard/CLAUDE.md")
Or one item declares "orch/daemon/**" and another declares "orch/daemon/batch_manager.py"
Then find_blocking_items still reports them as blocking
And the existing test_blocks_one_in_flight / test_blocks_multiple_in_flight regression tests still pass
```

### AC4: Event message no longer misleads

```
Given the fix is applied
When the daemon holds an item due to scope overlap
Then the daemon_events message names a glob that is genuinely produced by globs_intersect
(by construction — the only code path remaining names real intersecting globs)
```

## Regression Prevention

1. **Codified reproduction**: The two real CR-00057↔CR-00060 path pairs are baked into `TestI00099SiblingDirNoLongerBlocks` as named cases. Any future re-introduction of the sibling rule (or an equivalent structural fallback) would re-break these tests immediately.
2. **Dead code deleted, not commented out**: `_same_parent` and its caller branch are removed entirely. There is no dormant code path for someone to "re-enable" without writing a fresh function and a fresh design pass.
3. **Module docstring records the decision**: `orch/daemon/scope_overlap.py`'s top docstring gains a `2026-05-18 (I-00099)` note explaining why the sibling rule was removed (false-positive holds on large dirs) and what the safety net is (git merge resolves real text conflicts; items that need module-level exclusion declare `dir/**` explicitly).
4. **No new heuristics introduced**: The fix is purely subtractive. No new threshold knobs, no new allowlists, no new state — the only mental model an operator needs is "if `globs_intersect` returns non-empty, you overlap".

## Dependencies

- **Depends on**: None
- **Blocks**: None (CR-00060 was already manually unblocked by removing the offending paths from its scope; this fix means future items won't need the same workaround)

## Impacted Paths

- `orch/daemon/scope_overlap.py`
- `tests/unit/daemon/test_scope_overlap.py`

## TDD Approach

- **Reproducing test**: `TestI00099SiblingDirNoLongerBlocks::test_two_different_docs_in_same_dir_do_not_block` and `::test_two_different_daemon_modules_do_not_block` — both fail against pre-S01 code (the sibling rule returns `[("CR-00057", [...])]`), both pass after S01.
- **Unit tests**: Live in `tests/unit/daemon/test_scope_overlap.py`. The two new tests above plus the existing exact-file and glob-anchor tests (which must continue to pass) prove the rule narrowed correctly.
- **Integration tests**: No new integration tests. The existing `tests/integration/daemon/test_batch_manager_scope_gate.py` exercises `_launch_pending_items`'s use of `find_blocking_items` and must continue to pass after the rule change. The Tests step verifies this by running `uv run pytest tests/integration/daemon/test_batch_manager_scope_gate.py -v` as part of its targeted verification.
- **Deletions**: `test_non_test_sibling_still_blocks` (asserts the buggy behaviour) is removed. The Tests step prompt explicitly calls this out so the agent doesn't try to "rescue" it.
- **Docstring updates**: `TestI00071RegressionBatch00078`'s class docstring references the sibling rule; refresh it to note that under the new rule, the test-path stripping behaviour it validates is still meaningful for `globs_intersect` even though the sibling-case it was originally protecting is gone.

## Notes

- **Why we're not adopting the small-fanout or allowlist alternatives.** Both reintroduce arbitrary thresholds that operators have to reason about and maintain. The pure subtractive fix matches the project's preference for explicit `impacted_paths` declarations (you say what you touch; the gate trusts you).
- **Merge-time scope_gate is off for iw-ai-core.** This was confirmed during the user's unblock investigation: `.iw-orch.json` does not contain `scope_gate_enabled`, so the merge-queue mirror won't enforce anything either. The fix is purely about the launch-time gate.
- **No back-fill of misleading historical events.** `daemon_events` is append-only; past `item_held_for_scope` rows stay as written. Only future events benefit from the cleaner gate.
- **Migration lock** at design time: `free` (no Database step planned).
