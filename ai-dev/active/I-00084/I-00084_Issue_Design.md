# I-00084: Stale `origin/main` ref breaks `make diff-coverage` in worktrees

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-15
**Reported By**: sergio (operator); diagnosed during CR-00053 manual rescue
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. No Docker usage.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migration impact.)

## Description

`make diff-coverage` invokes `diff-cover ... --compare-branch=origin/main`,
which computes a "diff" between the worktree (working copy + HEAD) and
the `origin/main` ref. This project's setup is local-only — nothing
pushes to GitHub — so `origin/main` ages indefinitely. Every locally
merged item since the last manual `git fetch` shows up in every
worktree's "diff", inflating the file list and dragging diff-coverage
below the 90% threshold for reasons unrelated to the work item.

CR-00053's diff-coverage saw 18 commits' worth of unrelated files
(CR-00048 through CR-00052, F-00082, etc.), reporting 75% coverage on a
diff of 243 lines — when the actual CR-00053 diff was 40 lines at 92%.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard
rules. Most relevant: `Makefile` `diff-coverage` target and
`executor/setup_worktree.sh` (worktree creation site).

## Steps to Reproduce

1. On a fresh local clone, do not push anything to GitHub. Approve and
   merge any item — observe `git log origin/main` does not advance.
2. Approve a new item; let the daemon create its worktree.
3. From inside the worktree: `make diff-coverage`.
4. Observe: `diff-cover` reports many files and a low coverage number;
   the file list contains items the worktree never touched.

**Expected**: `diff-cover` should compare against the actual current
`main` branch, so the diff is just this item's changes.

**Actual**: `diff-cover` compares against the stale `origin/main` ref,
which is far behind local `main`, so the diff includes every locally
merged commit since the last `git push`.

## Root Cause Analysis

The Makefile target hardcodes `--compare-branch=origin/main`:

```
diff-coverage:
    ...
    uv run diff-cover tests/output/coverage/coverage-combined.xml \
      --compare-branch=origin/main --fail-under=90
```

This is fine in CI (where `origin/main` always reflects the current
remote) but incorrect for a local-only daemon-driven setup where
`origin/main` is never pushed to and `main` is the source of truth.

There is no setup step in `executor/setup_worktree.sh` that synchronises
`origin/main` with local `main`. A one-liner — `git fetch . main:refs/remotes/origin/main`
— resolves it.

## Affected Components

| Component | Impact |
|-----------|--------|
| `executor/setup_worktree.sh` | Missing `origin/main` sync at worktree-create time |
| `Makefile` (`diff-coverage` target) | Could optionally fall back to local `main` if `origin/main` is stale, but the cleaner fix is at worktree create |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Pipeline | Add `git fetch . main:refs/remotes/origin/main` to `executor/setup_worktree.sh` immediately after `git worktree add`; add the same one-liner as a safeguard at the top of the `diff-coverage` Makefile target | — |
| S02 | CodeReview | Per-agent review of S01 | — |
| S03 | Tests | Reproduction test: simulate stale origin/main, run setup_worktree, assert origin/main matches main after creation | — |
| S04 | CodeReview | Per-agent review of S03 | — |
| S05 | CodeReview_Final | Cross-agent global review | — |
| S06..S13 | QV Gates | lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S14 | SelfAssess | Self-assessment via iw-item-analyze skill | — |

### Database Changes

- **New tables**: None.
- **Modified tables**: None.
- **Migration notes**: No schema impact.

### Code Changes

- **Files to modify**: `executor/setup_worktree.sh`, `Makefile`.
- **Nature of change**: insert a single `git fetch` line in two places.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00084_Issue_Design.md` | Design | This document |
| `I-00084_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00084_S01_Pipeline_prompt.md` | Prompt | S01 fix |
| `prompts/I-00084_S02_CodeReview_Pipeline_prompt.md` | Prompt | S02 review |
| `prompts/I-00084_S03_Tests_prompt.md` | Prompt | S03 tests |
| `prompts/I-00084_S04_CodeReview_Tests_prompt.md` | Prompt | S04 test review |
| `prompts/I-00084_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00084_S14_SelfAssess_prompt.md` | Prompt | S14 self-assess |

## Test to Reproduce

```python
def test_i00084_setup_worktree_syncs_origin_main(tmp_path):
    """After setup_worktree, the new worktree's origin/main ref must match
    local main, even if origin/main was stale beforehand.

    This test should FAIL before the fix and PASS after.
    """
    # Arrange — fake repo where origin/main lags local main by 5 commits
    repo = make_fake_repo(tmp_path)
    base_sha = simulate_commit(repo, "base")
    set_origin_main(repo, base_sha)  # origin/main intentionally stale
    for i in range(5):
        simulate_commit(repo, f"local-main-{i}")
    local_main_sha = current_head(repo)
    assert get_origin_main(repo) == base_sha, "precondition: origin/main is stale"

    # Act
    worktree_path = run_setup_worktree(repo, item_id="I-99001", branch="agent/foo")

    # Assert
    assert get_origin_main(repo, cwd=worktree_path) == local_main_sha, (
        f"setup_worktree must sync origin/main to local main; "
        f"got {get_origin_main(repo, cwd=worktree_path)} expected {local_main_sha}"
    )
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given local main is N commits ahead of origin/main
When the daemon creates a worktree for any item
Then within the worktree, origin/main matches local main
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/integration/test_setup_worktree_origin_main_sync.py passes
```

### AC3: `make diff-coverage` produces correct diffs

```
Given a worktree with the fix applied AND a small in-scope change
When `make diff-coverage` runs
Then the diff includes only the in-scope changed files (no spurious files from other locally-merged items)
```

## Regression Prevention

- Reproduction test pins the post-create state.
- Defensive `git fetch . main:refs/remotes/origin/main` at the top of the
  `Makefile` `diff-coverage` target (idempotent, fast, safe even if the
  worktree is already in sync) — protects against any future code path
  that creates a worktree without going through `setup_worktree.sh`.

## Dependencies

- **Depends on**: None.
- **Blocks**: I-00082 effectiveness (false-positive diff-coverage failures
  trigger fix-cycle agents that drift; both fixes together substantially
  reduce stuck-CR rate).

## Impacted Paths

- `executor/setup_worktree.sh`
- `Makefile`
- `tests/integration/test_setup_worktree_origin_main_sync.py`

## TDD Approach

- Reproducing test: as above, end-to-end via `setup_worktree.sh` invoked
  on a fake repo under `tmp_path`.
- Unit tests: not strictly required (the change is a single `git fetch`
  invocation).
- Integration tests: the reproduction test.

## Notes

This is the simplest of the four sibling incidents (I-00082..I-00085).
The fix is two `git fetch` lines plus a regression test. Filed Medium
severity because:

- It silently inflates diff-coverage failures across every CR.
- The operator workaround is a single shell command, but undocumented.
- It interacts badly with I-00082 (drift triggers fix cycles, fix cycles
  drift further).

Concrete CR-00053 evidence: diff-cover reported 75% on 243 lines,
including unrelated files like `orch/cancel.py` and `orch/test_runner.py`
that CR-00053 never touched. After `git fetch . main:refs/remotes/origin/main`,
the same command reported 92% on 40 lines — the actual CR-00053 diff.
