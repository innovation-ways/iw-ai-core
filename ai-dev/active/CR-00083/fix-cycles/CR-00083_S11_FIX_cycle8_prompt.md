# CR-00083 S11 QV Fix Cycle 8/7

Quality gate S11 for work item CR-00083 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  tests/perf/**
  tests/perf/baselines/**
  Makefile
  pyproject.toml
  uv.lock
  .github/workflows/perf-budgets.yml
  docs/IW_AI_Core_Testing_Strategy.md
  skills/iw-ai-core-testing/**
  .claude/skills/iw-ai-core-testing/**
  ai-dev/work/TESTS_ENHANCEMENT.md
  orch/daemon/fix_cycle.py
  tests/assertion_free_baseline.txt
  tests/unit/test_llm_judge_script.py
  scripts/llm_judge_test_review.py
  tests/conftest.py
  dashboard/routers/worktrees.py
  tests/dashboard/test_alembic_guard_banner.py
  tests/dashboard/test_doc_job_log_endpoints.py
  tests/integration/test_doc_job_log_endpoints.py
  tests/integration/test_code_index_pipeline.py
  tests/dashboard/test_route_contract_sweep.py

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/CR-00083/**
  ai-dev/archive/CR-00083/**
  ai-dev/work/CR-00083/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/ai-dev/active/CR-00083/CR-00083_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: Process exited without reporting completion (PID dead)

**Gate report**:
```
...(truncated)...
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 900, in __connect
      with util.safe_reraise():
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/.venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py", line 121, in __exit__
      raise exc_value.with_traceback(exc_tb)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 896, in __connect
      self.dbapi_connection = connection = pool._invoke_creator(self)
                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/.venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py", line 667, in connect
      return dialect.connect(*cargs_tup, **cparams)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/.venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py", line 630, in connect
      return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/.venv/lib/python3.12/site-packages/psycopg/connection.py", line 122, in connect
      raise last_ex.with_traceback(None)
  sqlalchemy.exc.OperationalError: (psycopg.OperationalError) connection failed: connection to server at "127.0.0.1", port 51396 failed: Connection refused
  	Is the server running on that host and accepting TCP/IP connections?
  (Background on this error at: https://sqlalche.me/e/20/e3q8)

  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnhandledThreadExceptionWarning(msg))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/dashboard/test_route_contract_sweep.py::test_route_returns_no_5xx[GET /system/nav/worktree-badge]
FAILED tests/dashboard/test_doc_job_log_endpoints.py::TestDocJobLogStream::test_returns_sse_content_type
FAILED tests/dashboard/test_alembic_guard_banner.py::TestAlembicGuardBanner::test_banner_appears_when_db_behind_head
FAILED tests/dashboard/test_alembic_guard_banner.py::TestAlembicGuardBanner::test_no_banner_at_head
FAILED tests/integration/test_doc_job_log_endpoints.py::TestLogStream::test_log_stream_heartbeat
FAILED tests/integration/test_doc_job_log_endpoints.py::TestLogStream::test_log_stream_emits_lines_then_terminal
= 6 failed, 3234 passed, 29 skipped, 4 xfailed, 3 xpassed, 192 warnings in 295.33s (0:04:55) =
make: *** [Makefile:469: allure-integration] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make test-unit
```

After applying fixes, re-run this command to verify the issues are resolved.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Skim the section that covers this step's scope; quote-of-the-doc lives in this prompt when available.
2. **Diff your target file(s) against the spec** — list deviations explicitly before editing.
3. **Apply the minimum patch** to align code with the spec; the reported errors should resolve as a side effect of that alignment.
4. **If the errors disagree with the spec, the spec wins.** Note the disagreement in your output rather than silently following the errors.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.
5. **Post-edit cross-gate check (MANDATORY before exit).** When the
   failing gate is NOT lint/format, your edits may still introduce a
   new ruff violation that the next review run trips on. Before exiting,
   run `make format-check` and `make lint` and resolve any NEW violation
   your edits introduced (`uv run ruff format <file>` for format issues;
   targeted edit for lint). Diagnosed 2026-05-25 from CR-00082 S04's
   ping-pong between fix cycles where each agent re-broke the gate the
   previous one fixed.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
