# CR-00083 S12 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | diff-coverage      |
| Command      | `make diff-coverage` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 354       |

## Output (tail)

```
3240 passed, 29 skipped, 4 xfailed, 3 xpassed, 194 warnings in 354.95s (0:05:54)
uv run coverage xml -o tests/output/coverage/coverage-combined.xml
Wrote XML report to tests/output/coverage/coverage-combined.xml
uv run diff-cover tests/output/coverage/coverage-combined.xml --compare-branch=origin/main --fail-under=90
-------------
Diff Coverage
Diff: origin/main...HEAD, staged and unstaged changes
-------------
dashboard/app.py (100%)
dashboard/routers/docs.py (100%)
dashboard/routers/keep_alive.py (100%)
dashboard/routers/worktrees.py (100%)
orch/cli/doc_commands.py (100%)
orch/daemon/fix_cycle.py (97.1%): Missing lines 2724
orch/daemon/main.py (100%)
orch/daemon/project_registry.py (97.1%): Missing lines 446
orch/daemon/scope_amendment.py (100%)
-------------
Total:   119 lines
Missing: 2 lines
Coverage: 98%
-------------
```

## Notes

Diff coverage = 98% on 119 changed lines (above the 90% gate). The perf modules in `tests/perf/**` are new test files, not production code, so they do not contribute to covered lines. The diff-covered production lines come from previously merged work (`dashboard/`, `orch/daemon/`, `orch/cli/`) that incidentally fell within `origin/main...HEAD`. No new production code was introduced by CR-00083 — the gate confirms that.

## Verdict

```
pass
```
