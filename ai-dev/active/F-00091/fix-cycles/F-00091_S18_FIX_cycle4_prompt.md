# F-00091 S18 QV Fix Cycle 4/7

Quality gate S18 for work item F-00091 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  dashboard/templates/chat_assistant/panel.html
  dashboard/templates/chat_assistant/composer.html
  dashboard/static/chat_assistant/chat.js
  dashboard/static/chat_assistant/chat.css
  dashboard/static/styles.css
  dashboard/routers/chat.py
  dashboard/routers/projects.py
  orch/chat/context_usage.py
  orch/db/migrations/versions/**
  tests/dashboard/**
  tests/integration/**
  tests/unit/**

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/F-00091/**
  ai-dev/archive/F-00091/**
  ai-dev/work/F-00091/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/ai-dev/active/F-00091/F-00091_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
e "/usr/lib/python3.12/threading.py", line 1010, in run
      self._target(*self._args, **self._kwargs)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/dashboard/routers/oss.py", line 535, in <lambda>
      target=lambda: asyncio.run(_run_oss_job(job.id)),
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
      return runner.run(main)
             ^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
      return self._loop.run_until_complete(task)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/base_events.py", line 687, in run_until_complete
      return future.result()
             ^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/dashboard/routers/oss.py", line 413, in _run_oss_job
      from orch.db.session import SessionLocal
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/orch/db/session.py", line 98, in __getattr__
      return _get_session_local()
             ^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/orch/db/session.py", line 62, in _get_session_local
      bind=_get_engine(),
           ^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/orch/db/session.py", line 47, in _get_engine
      _engine = safe_create_engine(
                ^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/orch/db/live_db_guard.py", line 163, in safe_create_engine
      assert_engine_url_allowed(url)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/orch/db/live_db_guard.py", line 134, in assert_engine_url_allowed
      raise LiveDbConnectionRefusedError(
  orch.db.live_db_guard.LiveDbConnectionRefusedError: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnhandledThreadExceptionWarning(msg))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_lock_timeout_failure_under_short_timeout
ERROR tests/integration/db/test_safe_migrate_self_blocker.py::test_lock_timeout_set_on_apply_connection
= 3313 passed, 29 skipped, 5 xfailed, 3 xpassed, 192 warnings, 2 errors in 307.48s (0:05:07) =
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
make allure-integration
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
