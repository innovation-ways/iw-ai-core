# I-00109 S12 QV Fix Cycle 1/5

Quality gate S12 for work item I-00109 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  dashboard/routers/docs.py
  tests/dashboard/test_route_contract_sweep.py
  tests/dashboard/test_docs_pdf_cache_failure.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00109/ai-dev/active/I-00109/I-00109_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: diff-coverage failed: exit=2

**Gate report**:
```
...(truncated)...
, 92, 97, 102, 113, 123, 127, 131, 138, 142, 198
orch/services/__init__.py                     16     12      4      0    20%   27-69
orch/skills/init_project.py                   83      6     14      2    88%   27, 177-181
orch/skills/sync.py                           83      5     30      4    92%   39, 54->58, 56-57, 89, 93
orch/skills/sync_agents.py                    60      5     10      0    93%   52-53, 118-120
orch/staleness/alembic_check.py               95     14     32      5    85%   98->94, 124, 126, 227-229, 267-278, 287-294, 327->330
orch/staleness/config.py                      85      1     32      1    98%   48
orch/staleness/detection.py                  192     51     64     12    75%   41-45, 50-57, 65-66, 75-83, 106-107, 134, 142, 178-179, 194->198, 214, 236-238, 251, 277->275, 308-313, 319, 328-330, 351, 361-363, 390, 394-396, 402, 427->423, 430-431
orch/staleness/git_lookup.py                  58     15     16      2    77%   78-83, 152-157, 172, 176-177
orch/staleness/service.py                     94     14     24      1    87%   41-43, 140-145, 178-182, 245-247, 259-261
orch/test_runner.py                          360    229     70     10    36%   47-48, 54-60, 78, 87->95, 128-162, 169, 185, 208-222, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 589, 628, 640-641, 657-679, 691-700
orch/utils/log_capture.py                     33      4      8      1    88%   43-46, 58->60
--------------------------------------------------------------------------------------
TOTAL                                      26378  11595   7640    648    53%

35 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
=========================== short test summary info ============================
ERROR tests/integration/test_compose_split.py - subprocess.TimeoutExpired: Co...
ERROR tests/integration/test_compose_split.py - subprocess.TimeoutExpired: Co...
ERROR tests/integration/test_compose_split.py - subprocess.TimeoutExpired: Co...
ERROR tests/integration/test_compose_split.py - subprocess.TimeoutExpired: Co...
ERROR tests/integration/test_compose_split.py - subprocess.TimeoutExpired: Co...
ERROR tests/integration/test_compose_split.py - subprocess.TimeoutExpired: Co...
ERROR gw28 - Different tests were collected between gw14 and gw28. The differ...
ERROR gw24 - Different tests were collected between gw14 and gw24. The differ...
ERROR gw8 - Different tests were collected between gw14 and gw8. The differen...
ERROR gw12 - Different tests were collected between gw14 and gw12. The differ...
ERROR gw3 - Different tests were collected between gw14 and gw3. The differen...
ERROR gw13 - Different tests were collected between gw14 and gw13. The differ...
32 warnings, 12 errors in 110.99s (0:01:50)
make: *** [Makefile:191: diff-coverage] Error 1
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


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
