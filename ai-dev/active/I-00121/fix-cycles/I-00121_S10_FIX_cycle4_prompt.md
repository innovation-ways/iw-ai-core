# I-00121 S10 QV Fix Cycle 4/5

Quality gate S10 for work item I-00121 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/test_runner.py
  tests/unit/test_test_runner_allure_env.py
  tests/integration/test_test_runner_report_persistence.py

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/I-00121/**
  ai-dev/archive/I-00121/**
  ai-dev/work/I-00121/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00121/ai-dev/active/I-00121/I-00121_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: unit-tests failed: exit=2

**Unparseable output** (always surfaces):
  uv run pytest tests/unit/ --cov=orch --cov=dashboard --cov=executor --cov-report=term-missing:skip-covered --cov-report=html:tests/output/coverage/htmlcov --cov-report=xml:tests/output/coverage/coverage.xml --cov-report=json:tests/output/coverage/coverage.json -v
  platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00121/.venv/bin/python
  cachedir: .pytest_cache
  benchmark: 4.0.0 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
  hypothesis profile 'default'
  Using --randomly-seed=1941758070
  rootdir: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00121
  configfile: pyproject.toml
  plugins: timeout-2.4.0, asyncio-1.3.0, cov-7.1.0, respx-0.22.0, xdist-3.8.0, allure-pytest-2.15.3, Faker-40.13.0, schemathesis-4.19.0, rerunfailures-15.1, benchmark-4.0.0, anyio-4.13.0, hypothesis-6.152.7, randomly-4.1.0
  asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
  collecting ... collected 3722 items
  _ ERROR at setup of TestChatSummarizationJobConstraints.test_unique_partial_in_flight_constraint _
  self = <docker.api.client.APIClient object at 0x72a8d8f592e0>
  response = <Response [500]>
      def _raise_for_status(self, response):
          """Raises stored :class:`APIError`, if one occurred."""
          try:
  >           response.raise_for_status()
  .venv/lib/python3.12/site-packages/docker/api/client.py:275: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  self = <Response [500]>
      def raise_for_status(self):
          """Raises :class:`HTTPError`, if one occurred."""
          http_error_msg = ""
          if isinstance(self.reason, bytes):
              try:
                  reason = self.reason.decode("utf-8")
              except UnicodeDecodeError:
                  reason = self.reason.decode("iso-8859-1")
          else:
              reason = self.reason
          if 400 <= self.status_code < 500:
              http_error_msg = (
                  f"{self.status_code} Client Error: {reason} for url: {self.url}"
              )
          elif 500 <= self.status_code < 600:
              http_error_msg = (
                  f"{self.status_code} Server Error: {reason} for url: {self.url}"
              )
          if http_error_msg:
  ...(1 lines omitted)...
  orch/rag/symbol_gen.py                         72     56     22      0    17%   50-68, 71-91, 96-104, 107-111, 114-116, 119-120, 133-144
  orch/regression_link_service.py                83     64     32      0    17%   75-108, 137-230
  orch/self_assess.py                            98     13     42     13    81%   79, 84, 88, 92, 97, 102, 113, 123, 127, 131, 138, 142, 198
  orch/services/__init__.py                      16     12      4      0    20%   27-69
  orch/skills/init_project.py                    83      6     14      2    88%   27, 177-181
  orch/skills/sync.py                            83      5     30      4    92%   39, 54->58, 56-57, 89, 93
  orch/skills/sync_agents.py                     60      5     10      0    93%   52-53, 118-120
  orch/staleness/alembic_check.py                95     14     32      5    85%   98->94, 124, 126, 227-229, 267-278, 287-294, 327->330
  orch/staleness/config.py                       85      1     32      1    98%   48
  orch/staleness/detection.py                   192     51     64     12    75%   41-45, 50-57, 65-66, 75-83, 106-107, 134, 142, 178-179, 194->198, 214, 236-238, 251, 277->275, 308-313, 319, 328-330, 351, 361-363, 390, 394-396, 402, 427->423, 430-431
  orch/staleness/git_lookup.py                   58     15     16      2    77%   78-83, 152-157, 172, 176-177
  orch/staleness/service.py                      94     14     24      1    87%   41-43, 140-145, 178-182, 245-247, 259-261
  orch/test_health_service.py                   137     51     28      5    61%   38, 41-43, 74-75, 102-104, 109-110, 114->124, 121-122, 157-159, 172-204, 280, 295-318, 326-346, 356-365
  orch/test_runner.py                           365    234     72      8    35%   88-89, 95-101, 120, 159-193, 200, 220-223, 246-260, 276-490, 498-523, 533-564, 576-589, 601-608, 627, 666, 678-679, 695-717, 729-738
  orch/utils/log_capture.py                      33      4      8      1    88%   43-46, 58->60
  ---------------------------------------------------------------------------------------
  TOTAL                                       27712  12333   8040    665    52%
  35 files skipped due to complete coverage.
  Coverage HTML written to dir tests/output/coverage/htmlcov
  Coverage XML written to file tests/output/coverage/coverage.xml
  Coverage JSON written to file tests/output/coverage/coverage.json
  Required test coverage of 50.0% reached. Total coverage: 52.29%
  ERROR tests/unit/db/test_chat_summarization_job_model.py::TestChatSummarizationJobConstraints::test_unique_partial_in_flight_constraint
  ERROR tests/unit/db/test_chat_summarization_job_model.py::TestChatSummarizationJobDefaults::test_default_status_is_queued
  ERROR tests/unit/test_jobs_aggregator.py::test_status_filter_narrows_results
  ERROR tests/unit/test_jobs_aggregator.py::test_empty_state_returns_empty_list
  ERROR tests/unit/test_jobs_aggregator.py::test_research_published_normalises_to_completed
  ERROR tests/unit/test_jobs_aggregator.py::test_sort_descending - docker.error...
  ERROR tests/unit/test_jobs_aggregator.py::test_date_range_filter - docker.err...
  ERROR tests/unit/test_jobs_aggregator.py::test_batch_executing_normalises_to_running
  ERROR tests/unit/test_jobs_aggregator.py::test_type_filter_narrows_to_one - d...
  ERROR tests/unit/test_jobs_aggregator.py::test_get_job_returns_correct_row_per_type
  ERROR tests/unit/test_jobs_aggregator.py::test_four_source_union - docker.err...
  ERROR tests/unit/test_jobs_aggregator.py::test_pagination_returns_correct_page
  ERROR tests/unit/test_jobs_aggregator.py::test_sort_ascending - docker.errors...
  ERROR tests/unit/db/test_work_item_impacted_paths.py::TestWorkItemImpactedPathsDefault::test_impacted_paths_can_be_set_explicitly
  ERROR tests/unit/db/test_work_item_impacted_paths.py::TestWorkItemImpactedPathsDefault::test_impacted_paths_not_null_constraint
  ERROR tests/unit/db/test_work_item_impacted_paths.py::TestWorkItemImpactedPathsDefault::test_impacted_paths_defaults_to_empty_list
  = 3692 passed, 6 skipped, 7 xfailed, 1 xpassed, 46 warnings, 16 errors in 81.74s (0:01:21) =
  make: *** [Makefile:121: test-unit] Error 1


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
