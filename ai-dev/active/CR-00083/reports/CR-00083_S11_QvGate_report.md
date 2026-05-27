# CR-00083 S11 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | integration-tests      |
| Command      | `make test-integration` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 294       |

## Output (tail)

```
= 3240 passed, 29 skipped, 4 xfailed, 3 xpassed, 194 warnings in 294.74s (0:04:54) =
```

## Notes

Re-run of the integration suite after the fix-cycle 5–7 patches that:

1. Patched `_get_session_local` (not just `_engine` + `_session_local`) in the four
   dashboard / integration test fixtures whose routes call
   `dashboard.routers.worktrees._compute_dirty_count` indirectly. The earlier
   patches only reset the module-level `_session_local` global, but
   `worktrees.py:_compute_dirty_count` lazy-imports `get_session`, which calls
   `_get_session_local()` directly — and Python's name lookup at call time picks
   up the production sessionmaker captured during test-collection import unless
   the function itself is monkeypatched.
2. Added `--timeout=600` to integration-test Makefile targets to keep wall-clock
   headroom for the dashboard contract sweep + perf-stack collection cost.

Confirmed locally with `make test-integration` (xdist `-n auto`, timeout 600):

```
= 3240 passed, 29 skipped, 4 xfailed, 3 xpassed, 194 warnings in 294.74s =
```

The six previously-failing tests now pass:

- `tests/dashboard/test_route_contract_sweep.py::test_route_returns_no_5xx[GET /system/nav/worktree-badge]`
- `tests/dashboard/test_doc_job_log_endpoints.py::TestDocJobLogStream::test_returns_sse_content_type`
- `tests/dashboard/test_alembic_guard_banner.py::TestAlembicGuardBanner::test_banner_appears_when_db_behind_head`
- `tests/dashboard/test_alembic_guard_banner.py::TestAlembicGuardBanner::test_no_banner_at_head`
- `tests/integration/test_doc_job_log_endpoints.py::TestLogStream::test_log_stream_heartbeat`
- `tests/integration/test_doc_job_log_endpoints.py::TestLogStream::test_log_stream_emits_lines_then_terminal`

## Verdict

```
pass
```
