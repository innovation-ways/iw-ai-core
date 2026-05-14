# CR-00050 S08 QV Fix Cycle 1/5

Quality gate S08 for work item CR-00050 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00050/ai-dev/active/CR-00050/CR-00050_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: unit-tests failed: exit=2

**New Failures**:
  [test] tests/unit/test_security_targets.py::test_workflow_actions_pinned_to_sha
**Unparseable output** (always surfaces):
  uv run pytest tests/unit/ -v
  platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00050/.venv/bin/python
  cachedir: .pytest_cache
  rootdir: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00050
  configfile: pyproject.toml
  plugins: timeout-2.4.0, asyncio-1.3.0, cov-7.1.0, xdist-3.8.0, allure-pytest-2.15.3, Faker-40.13.0, anyio-4.13.0
  asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
  collecting ... collected 2812 items
  _____________________ test_workflow_actions_pinned_to_sha ______________________
      def test_workflow_actions_pinned_to_sha() -> None:
          text = WORKFLOW.read_text()
          pattern = re.compile(r"uses:\s*([\w./-]+)@([\w./-]+)")
          for action, ref in pattern.findall(text):
  >           assert SHA_RE.match(ref), (
                  f"Action {action!r} pinned to non-SHA ref {ref!r} — must be a 40-char commit SHA"
              )
  E           AssertionError: Action 'gitleaks/gitleaks-action' pinned to non-SHA ref '4dd7c0a5a7ad8cda5c7a0e7c3c3d7b0c5d9a4f1e2' — must be a 40-char commit SHA
  E           assert None
  E            +  where None = <built-in method match of re.Pattern object at 0x76a69d935700>('4dd7c0a5a7ad8cda5c7a0e7c3c3d7b0c5d9a4f1e2')
  E            +    where <built-in method match of re.Pattern object at 0x76a69d935700> = re.compile('^[0-9a-f]{40}$').match
  tests/unit/test_security_targets.py:61: AssertionError
  orch/db/models.py:225
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00050/orch/db/models.py:225: PytestCollectionWarning: cannot collect test class 'TestRunStatus' because it has a __init__ constructor (from: tests/unit/test_test_runner.py)
      class TestRunStatus(enum.Enum):
  tests/unit/test_code_qa_router_rerender.py: 1 warning
  tests/unit/test_qa_engine_hybrid_retrieval.py: 2 warnings
  tests/unit/test_qa_engine_render_cache.py: 4 warnings
  tests/unit/test_qa_v2_prompt_layout.py: 8 warnings
  tests/unit/test_qa_v2_relevance_filter_eval.py: 5 warnings
    <string>:9: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
  tests/unit/test_code_ui_routes.py::TestCodeIndexStream::test_sse_stream_returns_idle_when_no_runner_in_registry
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00050/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
      warnings.warn(
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_falls_back_when_module_filter_empty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00050/tests/unit/test_qa_engine.py:633: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_translates_dotted_module_path_to_filesystem_filter
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00050/tests/unit/test_qa_engine.py:731: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
  ...(1 lines omitted)...
  orch/oss/tool_probe.py                        44      4      8      2    88%   47-48, 56, 59
  orch/qv_gate_validator.py                    122     31     52      4    75%   51, 69, 93-94, 109, 127, 274-337
  orch/rag/chat_repo.py                        126     75     38      2    38%   38-67, 92-125, 141-165, 181-222, 258-260, 282-284, 302-319, 353, 365, 394-398
  orch/rag/classifier.py                        26      0      8      2    94%   74->78, 75->74
  orch/rag/condense.py                          32     10      6      1    66%   87-101
  orch/rag/config.py                            29      0      2      1    97%   92->94
  orch/rag/doc_indexer.py                      190    190     52      0     0%   8-399
  orch/rag/doc_job.py                          102    102     24      0     0%   6-212
  orch/rag/evidence.py                          41      3     10      2    86%   56-57, 61
  orch/rag/git_log_resolver.py                  34      1     12      1    96%   62
  orch/rag/index_gen.py                        120      6     46      3    95%   37, 48, 82->81, 204-207
  orch/rag/indexer.py                          225    133     76      7    36%   82, 87-94, 96-103, 105-112, 123-133, 144-169, 177-225, 240-291, 301-326, 360-361, 367->373, 391-403, 405->411
  orch/rag/job.py                              183    159     44      0    11%   34-43, 47, 50, 53-170, 179-206, 217-233, 236-259, 267-268, 283-336, 346-366, 377-413
  orch/rag/mapgen.py                           127     71     30      1    41%   147-273, 277-286, 390
  orch/rag/module_gen.py                       182     21     44      8    85%   98-101, 110-117, 124-125, 141, 144->148, 156->161, 157->156, 162->164, 167->169, 239-240, 470-474
  orch/rag/module_progress.py                   61     22     10      1    59%   41, 45-46, 76, 83, 87-88, 96-115
  orch/rag/parser.py                            84      4     36      2    95%   26-27, 106, 131
  orch/rag/qa.py                               344     93    142     14    71%   124-126, 192-200, 218, 227-229, 397, 415-471, 474-514, 517, 564-579, 625-644, 752->751, 768, 769->771, 780->779, 785->784, 808->807, 812->797
  orch/rag/symbol_gen.py                        72     56     22      0    17%   50-68, 71-91, 96-104, 107-111, 114-116, 119-120, 133-144
  orch/self_assess.py                           98     13     42     13    81%   79, 84, 88, 92, 97, 102, 113, 123, 127, 131, 138, 142, 198
  orch/services/__init__.py                     16     12      4      0    20%   27-69
  orch/skills/init_project.py                   83      6     14      2    88%   27, 177-181
  orch/skills/sync.py                           83      5     30      4    92%   39, 54->58, 56-57, 89, 93
  orch/skills/sync_agents.py                    39     11      6      1    64%   38-50
  orch/staleness/alembic_check.py               95     14     32      5    85%   98->94, 124, 126, 227-229, 267-278, 287-294, 327->330
  orch/staleness/config.py                      85      1     32      1    98%   48
  orch/staleness/detection.py                  192     51     64     12    75%   41-45, 50-57, 65-66, 75-83, 106-107, 134, 142, 178-179, 194->198, 214, 236-238, 251, 277->275, 308-313, 319, 328-330, 351, 361-363, 390, 394-396, 402, 427->423, 430-431
  orch/staleness/git_lookup.py                  58     15     16      2    77%   78-83, 152-157, 172, 176-177
  orch/staleness/service.py                     94     14     24      1    87%   41-43, 140-145, 178-182, 245-247, 259-261
  orch/test_runner.py                          360    229     70     10    36%   47-48, 54-60, 78, 87->95, 128-162, 169, 185, 208-222, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 589, 628, 640-641, 657-679, 691-700
  orch/utils/log_capture.py                     33      4      8      1    88%   43-46, 58->60
  --------------------------------------------------------------------------------------
  TOTAL                                      21908   9844   6174    526    52%
  28 files skipped due to complete coverage.
  Coverage HTML written to dir tests/output/coverage/htmlcov
  Coverage XML written to file tests/output/coverage/coverage.xml
  Coverage JSON written to file tests/output/coverage/coverage.json
  Required test coverage of 50.0% reached. Total coverage: 51.82%
  = 1 failed, 2800 passed, 4 skipped, 5 xfailed, 2 xpassed, 46 warnings in 63.92s (0:01:03) =
  make: *** [Makefile:79: test-unit] Error 1


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


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
