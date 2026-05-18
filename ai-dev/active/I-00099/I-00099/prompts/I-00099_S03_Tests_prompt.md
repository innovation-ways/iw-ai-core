# I-00099_S03_Tests_prompt

**Work Item**: I-00099 -- Scope-overlap sibling-dir rule generates false-positive cross-batch holds
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures are exempt; mutating docker commands are not allowed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00099 --json`.
- `ai-dev/active/I-00099/I-00099_Issue_Design.md` — design document, especially the `Test to Reproduce` and `TDD Approach` sections
- `ai-dev/work/I-00099/reports/I-00099_S01_Backend_report.md` — S01 report
- `ai-dev/work/I-00099/reports/I-00099_S02_CodeReview_report.md` — S02 review
- `tests/unit/daemon/test_scope_overlap.py` — file you will modify
- `orch/daemon/scope_overlap.py` — module under test (read-only here)
- `skills/iw-ai-core-testing/SKILL.md` — assertion-strength + test red-flag rules. **REQUIRED reading before writing any test.**

## Output Files

- `ai-dev/work/I-00099/reports/I-00099_S03_Tests_report.md` — Step report

## Context

You are writing the **reproduction + regression tests** for I-00099. The Backend step (S01) has already removed the sibling-directory fallback from `orch/daemon/scope_overlap.py`. Your job is to codify the bug's reproduction so it can never silently come back, and to confirm the remaining glob-intersection rules still block correctly.

This is a `tests-impl` step. You are exempt from RED-first TDD (the production change already exists). Your job is coverage + semantic correctness.

## Requirements

### 1. Add `TestI00099SiblingDirNoLongerBlocks` class

In `tests/unit/daemon/test_scope_overlap.py`, add a new test class **after** the existing `TestI00071RegressionBatch00078` class:

```python
class TestI00099SiblingDirNoLongerBlocks:
    """I-00099 regression — sibling-directory false-positive holds.

    Two items that each touch a different file in a shared parent directory
    must not block each other. The pre-fix code's _same_parent fallback
    fired for any two files sharing a parent dir; this is now removed.
    Items that genuinely need module-level exclusion must declare an
    explicit glob (dir/**) or the exact same file.
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

    def test_exact_file_match_still_blocks(self) -> None:
        """Sanity: when two items declare the EXACT same file, they still block."""
        candidate_paths = ["dashboard/CLAUDE.md"]
        in_flight = [
            ("I-00069", ["dashboard/CLAUDE.md"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        assert len(result) == 1
        assert result[0][0] == "I-00069"
        assert "dashboard/CLAUDE.md" in result[0][1]

    def test_glob_anchor_still_blocks_file_under_anchor(self) -> None:
        """Sanity: an in-flight item declaring 'orch/daemon/**' blocks a candidate
        touching any file under that anchor. globs_intersect must still catch this."""
        candidate_paths = ["orch/daemon/batch_manager.py"]
        in_flight = [
            ("I-00070", ["orch/daemon/**"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        assert len(result) == 1
        assert result[0][0] == "I-00070"

    def test_glob_anchor_other_direction_still_blocks(self) -> None:
        """Sanity: candidate declares 'orch/daemon/**' and in-flight names a specific
        file in that tree. Must still block."""
        candidate_paths = ["orch/daemon/**"]
        in_flight = [
            ("I-00071", ["orch/daemon/batch_manager.py"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        assert len(result) == 1
        assert result[0][0] == "I-00071"
```

### 2. DELETE `test_non_test_sibling_still_blocks`

The existing test `TestI00071RegressionBatch00078::test_non_test_sibling_still_blocks` (around line 275) asserts the **buggy** behaviour we just removed: that two non-test prod files sharing a parent dir block each other. With the sibling rule gone, that test would now fail — and even if it passed, it would be locking in behaviour we explicitly chose to abandon.

**Delete the entire test method.** Do NOT comment it out. Do NOT rename it.

After the deletion, `TestI00071RegressionBatch00078` will contain only the two test-path-stripping tests (`test_two_items_both_only_test_files_under_same_dir_do_not_block` and `test_mixed_test_and_prod_paths_test_only_candidate_still_not_blocked`). Both must continue to pass — they exercise `_strip_test_globs`, which is still in the code path.

### 3. Refresh `TestI00071RegressionBatch00078` class docstring

The class docstring currently reads:

> The sibling-directory check in find_blocking_items must not fire when both the candidate and in-flight item declare ONLY test files under tests/dashboard/. The sibling check uses _strip_test_globs on both sides before comparing, so test paths are excluded from parent-directory comparison.

Rewrite it to reflect the post-I-00099 reality:

```python
class TestI00071RegressionBatch00078:
    """I-00071 regression — test-path stripping in find_blocking_items.

    Test-path globs (tests/, conftest, *.test.*, *.spec.*, …) are stripped
    from both sides BEFORE globs_intersect runs, so two items whose ONLY
    declared paths are test files cannot block each other even when they
    name the same file or share a glob anchor.

    Originally added (I-00071) to protect against the sibling-directory
    rule firing on tests/dashboard/* paths. The sibling rule was removed
    in I-00099 (2026-05-18); _strip_test_globs is still meaningful as a
    guard against test-file overlap registering as a launch-time block —
    test agents legitimately edit each other's files (fixture refactors,
    shared conftest tweaks) and shouldn't serialise on that.
    """
```

### 4. Verify the design's CR-00057↔CR-00060 reproduction cases use the exact path strings

Double-check the reproduction test strings against the design document:

- `docs/IW_AI_Core_Testing_Strategy.md` ↔ `docs/IW_AI_Core_AI_Assistant_Models.md`
- `orch/daemon/batch_manager.py` ↔ `orch/daemon/project_registry.py`

If you find a typo, fix it. If the design and your test disagree, the design wins — paste the exact strings from the design's `## Steps to Reproduce` and `## Root Cause Analysis` sections.

## Project Conventions

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` (mandatory):

- Pure-Python tests (no DB, no FastAPI, no FTS) live under `tests/unit/`. Our edits stay in `tests/unit/daemon/test_scope_overlap.py`.
- Assertions verify SEMANTIC correctness, not response shape. Compare the actual return shape (`result == []`, `len(result) == 1 and result[0][0] == "I-00069"`), not just truthiness.
- No mocks for the DB (there is no DB in this module).

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert result is not None` (shape only)
- BAD: `assert isinstance(result, list)` (shape only — empty list passes too)
- GOOD: `assert result == []` (semantic — verifies expected absence of blocking items)
- GOOD: `assert result[0][0] == "I-00069"` (semantic — verifies the specific blocking item)
- GOOD: `assert "dashboard/CLAUDE.md" in result[0][1]` (semantic — verifies the specific glob)

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

Populate `preflight` in the result contract.

## Test Verification (NON-NEGOTIABLE)

Run ONLY the modified file:

```bash
uv run pytest tests/unit/daemon/test_scope_overlap.py -v
```

Expected:
- All `TestI00099SiblingDirNoLongerBlocks` tests pass (5 tests).
- `TestI00071RegressionBatch00078`'s remaining 2 tests pass.
- All existing `TestGlobsIntersect` and `TestFindBlockingItems` tests pass.
- `test_non_test_sibling_still_blocks` no longer exists (the suite no longer references it).

Do NOT run `make test-unit` or `make test-integration` — those are S09/S10 QV gates with their own budgets. Running them here is a known cause of step timeouts (see I-00073/S03 post-mortem).

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00099",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/daemon/test_scope_overlap.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "N passed, 0 failed",
  "tdd_red_evidence": "n/a — coverage step on already-merged subtractive fix; new tests pass against post-S01 code",
  "blockers": [],
  "notes": "Deleted obsolete test_non_test_sibling_still_blocks; refreshed TestI00071RegressionBatch00078 docstring; added TestI00099SiblingDirNoLongerBlocks with 2 reproduction tests + 3 positive regression tests."
}
```
