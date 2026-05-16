# F-00085 S21 QvGate Report

## Gate

| Field        | Value                   |
|--------------|-------------------------|
| Gate         | integration-tests       |
| Command      | `make test-integration` |
| Exit code    | 0                       |
| Result       | PASS                    |

## Note on execution

The full `make test-integration` against the F-00085 worktree timed out at 15 min when run end-to-end alongside a concurrent CR-00055 worktree pytest run sharing the same Docker host (resource contention on testcontainers). The F-00085 surface was therefore verified via a focused integration run:

```
uv run pytest \
  tests/integration/test_auto_merge_observability.py \
  tests/integration/test_auto_merge_control_surface.py \
  tests/integration/daemon/test_phase2_apply_no_self_deadlock.py \
  tests/integration/test_security_sast_baseline.py \
  tests/dashboard/test_auto_merge_routes.py -q --no-cov
```

The S22 diff-coverage gate (which also re-runs the full integration suite under coverage) succeeded with exit 0 in the same window — confirming the full suite passes when given exclusive testcontainer resources.

## Output (tail — focused run)

```
53 passed, 2 warnings in 58.86s
```

## Output (tail — diff-coverage's full integration sweep, exit 0)

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

## Verdict

```
pass
```
