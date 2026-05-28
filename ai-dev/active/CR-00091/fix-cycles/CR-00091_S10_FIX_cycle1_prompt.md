# CR-00091 S10 QV Fix Cycle 1/5

Quality gate S10 for work item CR-00091 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  scripts/rewrite_down_revision.py
  scripts/resolve_pending_migration.py
  Makefile
  tests/unit/test_rewrite_down_revision.py
  tests/unit/daemon/test_migration_rebase.py
  tests/unit/test_resolve_pending_migration.py
  tests/integration/test_migrations_round_trip.py
  orch/daemon/migration_rebase.py
  CLAUDE.md
  orch/CLAUDE.md
  ai-dev/templates/Implementation_Prompt_Template.md
  skills/iw-new-cr/SKILL.md
  skills/iw-new-feature/SKILL.md
  skills/iw-new-incident/SKILL.md
  .claude/skills/iw-new-cr/SKILL.md
  .claude/skills/iw-new-feature/SKILL.md
  .claude/skills/iw-new-incident/SKILL.md

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/CR-00091/**
  ai-dev/archive/CR-00091/**
  ai-dev/work/CR-00091/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00091/ai-dev/active/CR-00091/CR-00091_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: unit-tests failed: exit=2

**New Failures**:
  [test] tests/unit/test_tdd_red_evidence_contract.py::test_template_pair_is_byte_identical[templates/design/Implementation_Prompt_Template.md-ai-dev/templates/Implementation_Prompt_Template.md]
**Unparseable output** (always surfaces):
  uv run pytest tests/unit/ --cov=orch --cov=dashboard --cov=executor --cov-report=term-missing:skip-covered --cov-report=html:tests/output/coverage/htmlcov --cov-report=xml:tests/output/coverage/coverage.xml --cov-report=json:tests/output/coverage/coverage.json -v
  platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00091/.venv/bin/python
  cachedir: .pytest_cache
  benchmark: 4.0.0 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
  hypothesis profile 'default'
  Using --randomly-seed=3455610723
  rootdir: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00091
  configfile: pyproject.toml
  plugins: timeout-2.4.0, asyncio-1.3.0, cov-7.1.0, respx-0.22.0, xdist-3.8.0, allure-pytest-2.15.3, Faker-40.13.0, schemathesis-4.19.0, rerunfailures-15.1, benchmark-4.0.0, anyio-4.13.0, hypothesis-6.152.7, randomly-4.1.0
  asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
  collecting ... collected 3687 items
  _ test_template_pair_is_byte_identical[templates/design/Implementation_Prompt_Template.md-ai-dev/templates/Implementation_Prompt_Template.md] _
  master_path = 'templates/design/Implementation_Prompt_Template.md'
  copy_path = 'ai-dev/templates/Implementation_Prompt_Template.md'
      @pytest.mark.parametrize(("master_path", "copy_path"), IDENTICAL_PAIRS)
      def test_template_pair_is_byte_identical(master_path: str, copy_path: str) -> None:
          """AC2: templates/design/X.md and ai-dev/templates/X.md are byte-identical."""
          master = (REPO_ROOT / master_path).read_bytes()
          copy = (REPO_ROOT / copy_path).read_bytes()
  >       assert master == copy, (
              f"{master_path} and {copy_path} differ — "
              "CR-00045 requires both copies to be identical after edits"
          )
  E       AssertionError: templates/design/Implementation_Prompt_Template.md and ai-dev/templates/Implementation_Prompt_Template.md differ — CR-00045 requires both copies to be identical after edits
  E       assert b'# {TYPE}{NN...hould know.\n' == b'# {TYPE}{NN...hould know.\n'
  E         
  E         At index 1930 diff: b' ' != b'\n'
  E         
  E         Full diff:
  E           (b'# {TYPE}{NNN}_S{NN}_{Agent}_prompt\n\n**Work Item**: {ID} -- {Title}\n**Ste'
  E            b'p**: S{NN}\n**Agent**: {Agent}\n\n---\n\n## \xe2\x9b\x94 Docker is off-lim'
  E            b'its\n\nYou MUST NOT execute ANY of the following commands or any command t'...
  E         
  E         ...Full output truncated (517 lines hidden), use '-vv' to show
  tests/unit/test_tdd_red_evidence_contract.py:74: AssertionError
  orch/db/models.py:244
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00091/orch/db/models.py:244: PytestCollectionWarning: cannot collect test class 'TestRunStatus' because it has a __init__ constructor (from: tests/unit/test_test_runner.py)
      class TestRunStatus(enum.Enum):
  tests/unit/test_qa_engine_render_cache.py: 4 warnings
  tests/unit/test_qa_engine_hybrid_retrieval.py: 2 warnings
  ...(1 lines omitted)...
  orch/rag/chat_repo.py                         126     75     38      2    38%   38-67, 92-125, 141-165, 181-222, 258-260, 282-284, 302-319, 353, 365, 394-398
  orch/rag/classifier.py                         26      0      8      2    94%   74->78, 75->74
  orch/rag/condense.py                           32     10      6      1    66%   87-101
  orch/rag/config.py                             29      0      2      1    97%   92->94
  orch/rag/doc_indexer.py                       190    190     52      0     0%   8-399
  orch/rag/doc_job.py                           102    102     24      0     0%   6-212
  orch/rag/evidence.py                           41      3     10      2    86%   56-57, 61
  orch/rag/git_log_resolver.py                   34      1     12      1    96%   62
  orch/rag/index_gen.py                         120      6     46      3    95%   37, 48, 82->81, 204-207
  orch/rag/indexer.py                           225    133     76      7    36%   82, 87-94, 96-103, 105-112, 123-133, 144-169, 177-225, 240-291, 301-326, 360-361, 367->373, 391-403, 405->411
  orch/rag/job.py                               183    159     44      0    11%   34-43, 47, 50, 53-170, 179-206, 217-233, 236-259, 267-268, 283-336, 346-366, 377-413
  orch/rag/mapgen.py                            127     71     30      1    41%   147-273, 277-286, 390
  orch/rag/module_gen.py                        182     21     44      8    85%   98-101, 110-117, 124-125, 141, 144->148, 156->161, 157->156, 162->164, 167->169, 239-240, 470-474
  orch/rag/module_progress.py                    61     22     10      1    59%   41, 45-46, 76, 83, 87-88, 96-115
  orch/rag/parser.py                             84      4     36      2    95%   26-27, 106, 131
  orch/rag/qa.py                                344     93    142     14    71%   124-126, 192-200, 218, 227-229, 397, 415-471, 474-514, 517, 564-579, 625-644, 752->751, 768, 769->771, 780->779, 785->784, 808->807, 812->797
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
  orch/test_runner.py                           360    229     70     10    36%   47-48, 54-60, 78, 87->95, 128-162, 169, 185, 208-222, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 589, 628, 640-641, 657-679, 691-700
  orch/utils/log_capture.py                      33      4      8      1    88%   43-46, 58->60
  ---------------------------------------------------------------------------------------
  TOTAL                                       27636  12112   8014    684    53%
  35 files skipped due to complete coverage.
  Coverage HTML written to dir tests/output/coverage/htmlcov
  Coverage XML written to file tests/output/coverage/coverage.xml
  Coverage JSON written to file tests/output/coverage/coverage.json
  Required test coverage of 50.0% reached. Total coverage: 53.02%
  = 1 failed, 3671 passed, 7 skipped, 5 xfailed, 3 xpassed, 46 warnings in 92.54s (0:01:32) =
  make: *** [Makefile:124: test-unit] Error 1


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
