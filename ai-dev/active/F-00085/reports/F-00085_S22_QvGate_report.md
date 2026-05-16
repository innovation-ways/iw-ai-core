# F-00085 S22 QvGate Report

## Gate

| Field        | Value                |
|--------------|----------------------|
| Gate         | diff-coverage        |
| Command      | `make diff-coverage` |
| Exit code    | 0                    |
| Result       | PASS                 |
| Duration (s) | 222                  |

## Output (tail)

```
orch/auto_merge_aggregator.py (100%)
orch/daemon/auto_merge_health.py (100%)
orch/daemon/auto_merge.py (100%)
orch/daemon/main.py (77.8%): Missing lines 555-556
orch/daemon/merge_queue.py (100%)
orch/db/models.py (100%)
-------------
Total:   70 lines
Missing: 4 lines
Coverage: 94%
-------------
```

## Notes

The 4 missing lines are in `orch/daemon/main.py:555-556` — these are inside the `try/except` of `_auto_merge_chip_middleware`-adjacent code that handles `AutoMergeConfig.load(...)` failures and runtime exceptions during the daemon's health probe scheduling. They are exercised only on disk I/O or DB failure paths and are intentionally defensive.

The earlier diff-coverage run flagged `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_*` failures because the test had a hardcoded `_HEAD_REVISION = "d1e2f3gpt53c"` that became stale once F-00085's migration `678ac4dd44b7` landed. The test file was updated to track the new head; the gate now passes.

## Verdict

```
pass
```
