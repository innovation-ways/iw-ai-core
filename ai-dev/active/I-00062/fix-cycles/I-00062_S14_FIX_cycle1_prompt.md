# I-00062 S14 QV Fix Cycle 1/5

Quality gate S14 for work item I-00062 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00062/ai-dev/active/I-00062/I-00062_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
        334    167    140     22    44%   43-48, 120-139, 147-155, 171-173, 185-186, 254-263, 273, 285, 289, 318, 321-329, 332-336, 339-344, 375-379, 407, 412-452, 455, 465, 477, 491-499, 502-517, 553-626, 644, 656, 664, 687->686, 701-708, 715->714, 720->719, 724, 726-728, 738->737, 742-763
orch/rag/symbol_gen.py                       72     56     22      0    17%   50-68, 71-91, 96-104, 107-111, 114-116, 119-120, 133-144
orch/self_assess.py                          98     20     42     18    71%   71, 79, 84, 88, 92, 97, 102, 107, 113, 117, 123, 127, 131, 138, 142, 172, 194-198, 223
orch/skills/init_project.py                  83     10     14      4    81%   27, 30-31, 107, 166, 177-181
orch/skills/sync.py                          83     48     30      4    35%   29-46, 52-57, 89, 92-141, 151->154
orch/skills/sync_agents.py                   39     11      6      1    64%   38-50
orch/staleness/alembic_check.py              95     71     32      0    19%   94-100, 114-126, 144-153, 179-330
orch/staleness/config.py                     85     21     32     10    65%   48, 51-54, 59, 62-74, 118, 122, 128, 176, 222->226, 227->230
orch/staleness/detection.py                 192    164     64      0    11%   41-45, 50-57, 62-66, 75-83, 101-107, 126-153, 170-187, 193-199, 213-257, 270-279, 301-313, 318-345, 350-380, 389-433
orch/staleness/git_lookup.py                 58     45     16      0    18%   57-95, 121-180
orch/staleness/service.py                    94     63     24      0    26%   41-43, 115-124, 132-212, 240-289
orch/test_runner.py                         360    318     70      2    10%   43-224, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 576-582, 587-594, 608-621, 626-632, 640-641, 657-679, 691-700
orch/utils/log_capture.py                    33     21      8      1    32%   22, 36-62
-------------------------------------------------------------------------------------
TOTAL                                     19328   6931   5346    753    60%

22 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 46.0% reached. Total coverage: 60.05%
=========================== short test summary info ============================
FAILED tests/dashboard/test_sse_client_wiring.py::TestNoDirectEventSourceInMigratedPages::test_no_direct_eventsource_to_global_stream[/project/iw-ai-core/batches]
FAILED tests/dashboard/test_sse_client_wiring.py::TestNoDirectEventSourceInMigratedPages::test_migrated_pages_register_iw_sse_handlers[/project/iw-ai-core/batches]
FAILED tests/dashboard/test_sse_client_wiring.py::TestOutOfScopePagesNotBroken::test_out_of_scope_pages_load_normally[/system/worktrees]
= 3 failed, 1671 passed, 15 skipped, 1 xfailed, 151 warnings in 401.67s (0:06:41) =
make: *** [Makefile:55: test-integration] Error 1
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


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
