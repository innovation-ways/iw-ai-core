# CR-00053 S15 QvGate Report

| Field        | Value                |
|--------------|----------------------|
| Gate         | diff-coverage        |
| Command      | `make diff-coverage` |
| Exit code    | 0                    |
| Result       | PASS                 |
| Mode         | manual (operator-driven) |

## Output (tail)

```
2370 passed, 33 skipped, 4 xfailed, 165 warnings in 667.82s (0:11:07)
uv run coverage xml -o tests/output/coverage/coverage-combined.xml
Wrote XML report to tests/output/coverage/coverage-combined.xml
uv run diff-cover tests/output/coverage/coverage-combined.xml --compare-branch=origin/main --fail-under=90
-------------
Diff Coverage
Diff: origin/main...HEAD, staged and unstaged changes
-------------
orch/cli/id_commands.py (90.6%): Missing lines 126,131-132
orch/db/models.py (100%)
-------------
Total:   40 lines
Missing: 3 lines
Coverage: 92%
-------------
```

## Verdict

```
pass
```

## Workflow note

The first 3 daemon attempts of this gate failed for two reasons that are both
side-effects of the daemon's setup, not CR-00053 quality issues:

1. **Stale `origin/main` ref** — local `main` was 18 commits ahead of `origin/main`
   (the user's setup is local-only; nothing pushes to GitHub). `diff-cover`
   computes the diff against `origin/main`, so when stale, every file changed
   in any of those 18 merges (CR-00048, CR-00049, F-00082, CR-00052, ...)
   appeared in CR-00053's "diff" — dragging coverage to 75%. Fix: in the
   worktree, `git fetch . main:refs/remotes/origin/main` updates the local
   `origin/main` ref to match local `main`. This is a one-shot operator action
   per worktree.
2. **`tests/integration/test_dashboard_actions.py` carry-over** — F-00082 made
   `executing` a valid cancel state, but the test's `executing` assertion was
   only updated as part of CR-00052's merge. This worktree's branch base
   includes F-00082 but not CR-00052's test fix, so the test failed.
   Operator applied the same one-line fix CR-00052's merge applied
   (`BatchStatus.executing` → `BatchStatus.completed`) with a comment.

The fix-cycle agent kept reverting the operator's `test_dashboard_actions.py`
edit on each retry because that file is outside CR-00053's `allowed_paths`.
That's correct behaviour in principle, but it locks CR-00053 in a deadlock
because the carry-over fix is genuinely required and the agent has no way to
distinguish "scope creep" from "necessary side effect."

Follow-up suggestions: (a) operator-driven `git fetch . main:refs/remotes/origin/main`
should be part of the daemon's pre-gate setup (or worktree creation); (b) the
fix-cycle agent should be allowed to escalate to operator when the only
remaining failure is in a file outside `allowed_paths` and the diff is
trivially required for compatibility with main.
