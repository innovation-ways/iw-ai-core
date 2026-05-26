# I-00113 S12 QV Fix Cycle 4/7

Quality gate S12 for work item I-00113 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/daemon/fix_cycle.py
  orch/daemon/step_monitor.py
  tests/unit/daemon/**
  tests/integration/daemon/**
  ai-dev/active/I-00113/**
  tests/unit/test_fix_cycle.py

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/I-00113/**
  ai-dev/archive/I-00113/**
  ai-dev/work/I-00113/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00113/ai-dev/active/I-00113/I-00113_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
arize.py                         19      3      0      0    84%   74-76
orch/rag/symbol_gen.py                        72     56     22      0    17%   50-68, 71-91, 96-104, 107-111, 114-116, 119-120, 133-144
orch/self_assess.py                           98     20     42     18    71%   71, 79, 84, 88, 92, 97, 102, 107, 113, 117, 123, 127, 131, 138, 142, 172, 194-198, 223
orch/skills/init_project.py                   83     10     14      4    81%   27, 30-31, 107, 166, 177-181
orch/skills/sync.py                           83     48     30      4    35%   29-46, 52-57, 89, 92-141, 151->154
orch/skills/sync_agents.py                    60     23     10      2    56%   43-55, 116-128
orch/staleness/alembic_check.py               95     71     32      0    19%   94-100, 114-126, 144-153, 179-330
orch/staleness/config.py                      85     21     32     10    65%   48, 51-54, 59, 62-74, 118, 122, 128, 176, 222->226, 227->230
orch/staleness/detection.py                  192    164     64      0    11%   41-45, 50-57, 62-66, 75-83, 101-107, 126-153, 170-187, 193-199, 213-257, 270-279, 301-313, 318-345, 350-380, 389-433
orch/staleness/git_lookup.py                  58     45     16      0    18%   57-95, 121-180
orch/staleness/service.py                     94     63     24      0    26%   41-43, 115-124, 132-212, 240-289
orch/test_runner.py                          360    322     70      0     9%   43-224, 238-452, 460-485, 495-526, 538-551, 563-570, 576-582, 587-594, 608-621, 626-632, 640-641, 657-679, 691-700
orch/utils/log_capture.py                     33     20      8      1    34%   36-62
--------------------------------------------------------------------------------------
TOTAL                                      26559   8258   7720   1258    65%

31 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 50.0% reached. Total coverage: 65.10%
=========================== short test summary info ============================
FAILED tests/dashboard/test_doc_job_log_endpoints.py::TestDocJobLogStream::test_returns_sse_content_type
FAILED tests/integration/test_doc_job_log_endpoints.py::TestLogStream::test_log_stream_emits_lines_then_terminal
FAILED tests/integration/test_doc_job_log_endpoints.py::TestLogStream::test_log_stream_heartbeat
FAILED tests/dashboard/test_route_contract_sweep.py::test_route_returns_no_5xx[GET /system/nav/worktree-badge]
FAILED tests/dashboard/test_alembic_guard_banner.py::TestAlembicGuardBanner::test_no_banner_at_head
FAILED tests/dashboard/test_alembic_guard_banner.py::TestAlembicGuardBanner::test_banner_appears_when_db_behind_head
= 6 failed, 3210 passed, 27 skipped, 2 deselected, 3 xfailed, 3 xpassed, 157 warnings in 1167.44s (0:19:27) =
make: *** [Makefile:129: test-integration] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make test-integration
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
