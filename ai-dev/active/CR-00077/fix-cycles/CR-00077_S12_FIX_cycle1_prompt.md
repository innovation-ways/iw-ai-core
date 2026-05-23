# CR-00077 S12 QV Fix Cycle 1/7

Quality gate S12 for work item CR-00077 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  dashboard/routers/batches.py
  dashboard/templates/fragments/batch_items_rows.html
  dashboard/templates/fragments/batch_overlap_modal.html
  dashboard/templates/pages/project/batch_detail.html
  dashboard/static/styles.css
  tests/dashboard/test_batch_overlap_modal.py
  tests/unit/test_batch_overlap_grouping.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00077/ai-dev/active/CR-00077/CR-00077_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
 81%   27, 30-31, 107, 166, 177-181
orch/skills/sync.py                           83     48     30      4    35%   29-46, 52-57, 89, 92-141, 151->154
orch/skills/sync_agents.py                    60     23     10      2    56%   43-55, 116-128
orch/staleness/alembic_check.py               95     71     32      0    19%   94-100, 114-126, 144-153, 179-330
orch/staleness/config.py                      85     21     32     10    65%   48, 51-54, 59, 62-74, 118, 122, 128, 176, 222->226, 227->230
orch/staleness/detection.py                  192    164     64      0    11%   41-45, 50-57, 62-66, 75-83, 101-107, 126-153, 170-187, 193-199, 213-257, 270-279, 301-313, 318-345, 350-380, 389-433
orch/staleness/git_lookup.py                  58     45     16      0    18%   57-95, 121-180
orch/staleness/service.py                     94     63     24      0    26%   41-43, 115-124, 132-212, 240-289
orch/test_runner.py                          360    318     70      2    10%   43-224, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 576-582, 587-594, 608-621, 626-632, 640-641, 657-679, 691-700
orch/utils/log_capture.py                     33     20      8      1    34%   36-62
--------------------------------------------------------------------------------------
TOTAL                                      26214   8018   7574   1236    66%

31 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 50.0% reached. Total coverage: 65.64%
=========================== short test summary info ============================
FAILED tests/dashboard/test_batches_router.py::TestGetScopeStatuses::test_held_event_returns_held_status
FAILED tests/dashboard/test_batches_router.py::TestGetScopeStatuses::test_both_events_held_precedence
FAILED tests/dashboard/test_batches_router.py::TestHttpPolicyAllowedPill::test_fragment_renders_held_pill_when_both_events_exist
FAILED tests/dashboard/test_batch_held_indicator.py::TestBatchItemRowsHeldReason::test_held_reason_appears_for_pending_item_with_hold_event
FAILED tests/dashboard/test_batch_held_indicator.py::TestGetHeldReasons::test_held_event_returns_reason_string
FAILED tests/dashboard/test_batch_held_indicator.py::TestHttpHeldIndicator::test_batch_items_fragment_renders_held_indicator
FAILED tests/dashboard/test_batch_overlap_ignore_endpoints.py::TestOverlapModalFiltersIgnored::test_get_modal_filters_ignored_files
FAILED tests/dashboard/test_batch_overlap_ignore_endpoints.py::TestIgnoreAllEndpoint::test_post_ignore_all_inserts_n_rows
FAILED tests/dashboard/test_batch_overlap_ignore_endpoints.py::TestIgnoreAllEndpoint::test_post_ignore_all_idempotent
= 9 failed, 3179 passed, 27 skipped, 2 deselected, 5 xfailed, 3 xpassed, 159 warnings in 1223.44s (0:20:23) =
make: *** [Makefile:107: test-integration] Error 1
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
