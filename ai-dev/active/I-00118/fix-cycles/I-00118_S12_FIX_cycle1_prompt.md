# I-00118 S12 QV Fix Cycle 1/5

Quality gate S12 for work item I-00118 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/daemon/qv_baseline.py
  orch/daemon/fix_cycle.py
  orch/daemon/batch_manager.py
  tests/unit/orch/daemon/test_qv_baseline.py
  tests/integration/daemon/test_baseline_qv_pipeline.py

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/I-00118/**
  ai-dev/archive/I-00118/**
  ai-dev/work/I-00118/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00118/ai-dev/active/I-00118/I-00118_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: diff-coverage failed: exit=2

**Gate report**:
```
...(truncated)...
py                         72     56     22      0    17%   50-68, 71-91, 96-104, 107-111, 114-116, 119-120, 133-144
orch/regression_link_service.py                83      7     32      5    90%   79, 144, 172, 185-186, 209->214, 211-212, 214->226
orch/self_assess.py                            98     13     42     13    81%   79, 84, 88, 92, 97, 102, 113, 123, 127, 131, 138, 142, 198
orch/skills/init_project.py                    83      6     14      2    88%   27, 177-181
orch/skills/sync.py                            83      5     30      4    92%   39, 54->58, 56-57, 89, 93
orch/skills/sync_agents.py                     60      5     10      0    93%   52-53, 118-120
orch/staleness/alembic_check.py                95     14     32      5    85%   98->94, 124, 126, 227-229, 267-278, 287-294, 327->330
orch/staleness/config.py                       85      1     32      1    98%   48
orch/staleness/detection.py                   192     51     64     12    75%   41-45, 50-57, 65-66, 75-83, 106-107, 134, 142, 178-179, 194->198, 214, 236-238, 251, 277->275, 308-313, 319, 328-330, 351, 361-363, 390, 394-396, 402, 427->423, 430-431
orch/staleness/git_lookup.py                   58     15     16      2    77%   78-83, 152-157, 172, 176-177
orch/staleness/service.py                      94     14     24      1    87%   41-43, 140-145, 178-182, 245-247, 259-261
orch/test_health_service.py                   137     35     28      5    72%   38, 41-43, 74-75, 102-104, 109-110, 114->124, 121-122, 157-159, 172-204
orch/test_runner.py                           360    229     70     10    36%   47-48, 54-60, 78, 87->95, 128-162, 169, 185, 208-222, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 589, 628, 640-641, 657-679, 691-700
orch/utils/log_capture.py                      33      4      8      1    88%   43-46, 58->60
---------------------------------------------------------------------------------------
TOTAL                                       27668   5124   8026   1109    79%

44 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
3348 passed, 29 skipped, 4 xfailed, 3 xpassed, 226 warnings in 343.16s (0:05:43)
uv run coverage xml -o tests/output/coverage/coverage-combined.xml
Wrote XML report to tests/output/coverage/coverage-combined.xml
uv run diff-cover tests/output/coverage/coverage-combined.xml --compare-branch=origin/main --fail-under=90
Failure. Coverage is below 90%.
-------------
Diff Coverage
Diff: origin/main...HEAD, staged and unstaged changes
-------------
orch/daemon/batch_manager.py (100%)
orch/daemon/fix_cycle.py (100%)
orch/daemon/qv_baseline.py (59.5%): Missing lines 290,293-294,299,313-314,316-323,325
-------------
Total:   39 lines
Missing: 15 lines
Coverage: 61%
-------------

make: *** [Makefile:225: diff-coverage] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make diff-coverage
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

## Post-Edit Gate (MANDATORY before exit)

After your final edit, run these two commands and fix any NEW violation
your edits introduced:

```bash
make format-check
make lint
```

If either command reports a violation in a file you touched this cycle,
resolve it before exiting — `uv run ruff format <file>` for format-check
failures, targeted edit for lint failures. Re-run both commands to confirm
green. The next review run WILL fail on these gates and burn another fix
cycle, so closing them now is strictly cheaper.

(Diagnosed 2026-05-25: in CR-00082 S04, cycle N reformatted
`playwright_wrapper.py` while cycle N+1 introduced a new line-length
violation in the same file; the loop never converged because no fix
agent self-checked these gates. This gate exists to break that loop.)



**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
