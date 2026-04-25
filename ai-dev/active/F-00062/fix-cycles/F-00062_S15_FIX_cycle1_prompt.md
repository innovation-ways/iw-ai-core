# F-00062 S15 QV Fix Cycle 1/5

Quality gate S15 for work item F-00062 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: lint failed: 12 ruff errors (2 fixable with --fix)

**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start F-00062 --step S15
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Started F-00062 step S15 (already in progress)
  $ make lint
  uv run ruff check .
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  TC003 Move standard library import `pathlib.Path` into a type-checking block
    --> orch/daemon/worktree_compose.py:37:21
     |
  35 | import tomllib
  36 | from dataclasses import dataclass
  37 | from pathlib import Path
     |                     ^^^^
  38 | from typing import Any
     |
  help: Move into type-checking block
  E501 Line too long (103 > 100)
     --> orch/daemon/worktree_compose.py:143:101
      |
  141 |         template_path=template_path,
  142 |         env_toml_path=env_toml_path,
  143 |         seed_script_path=seed_script_path if seed_script_path and seed_script_path.is_file() else None,
      |                                                                                                     ^^^
  144 |         rendered_compose_path=rendered_compose_path,
  145 |         compose_project_name=_compose_project_name(batch_item_id),
      |
  SLF001 Private member accessed: `_get_previous_job_watermark`
    --> orch/rag/doc_job.py:69:58
     |
  67 |             # has never been indexed (or the previous run failed), so index
  68 |             # everything from scratch.
  69 |             previous_watermark = await asyncio.to_thread(indexer._get_previous_job_watermark)
     |                                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  70 |             if previous_watermark is not None:
  71 |                 result = await asyncio.to_thread(
     |
  ARG001 Unused function argument: `project`
     --> orch/rag/doc_job.py:193:5
      |
  191 | def start_doc_index_job(
  192 |     job: DocIndexJob,
  193 |     project: Project,
      |     ^^^^^^^
  194 |     *,
  195 |     config: CodeUnderstandingConfig,
      |
  TC004 Move import `sqlalchemy.orm.sessionmaker` out of type-checking block. Import is used for more than type hinting.
     --> tests/integration/test_doc_index_job_runner.py:21:41
      |
   20 |     from sqlalchemy import Engine
   21 |     from sqlalchemy.orm import Session, sessionmaker
      |                                         ^^^^^^^^^^^^
   22 |
   23 | from orch.db.models import DocIndexJob, Project, WorkItem, WorkItemType
      |
     ::: tests/integration/test_doc_index_job_runner.py:147:32
      |
  145 |     ) -> None:
  146 |         """Runner enqueue + execute → status transitions queued → running → completed."""
  147 |         test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
      |                                ------------ Used at runtime here
  148 |
  149 |         project_id = "test-proj-runner-status"
      |
  help: Move out of type-checking block
  F541 [*] f-string without any placeholders
     --> tests/integration/test_doc_index_job_runner.py:211:23
      |
  209 |                 project_id=project.id,
  210 |                 id="WI-DUP-1",
  211 |                 title=f"Item WI-DUP-1",
      |                       ^^^^^^^^^^^^^^^^
  212 |                 type=WorkItemType.Feature,
  213 |                 functional_doc_content=f"Functional doc content for WI-DUP-1.",
      |
  help: Remove extraneous `f` prefix
  F541 [*] f-string without any placeholders
     --> tests/integration/test_doc_index_job_runner.py:213:40
      |
  211 |                 title=f"Item WI-DUP-1",
  212 |                 type=WorkItemType.Feature,
  213 |                 functional_doc_content=f"Functional doc content for WI-DUP-1.",
      |                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  214 |                 updated_at=now,
  215 |             )
      |
  help: Remove extraneous `f` prefix
  PT018 Assertion should be broken down into multiple parts
     --> tests/integration/test_doc_index_poller.py:375:13
      |
  373 |               launched = [j for j in [r1, r2] if j.status != "queued"]
  374 |               still_queued = [j for j in [r1, r2] if j.status == "queued"]
  375 | /             assert len(launched) == 1 and len(still_queued) == 1, (
  376 | |                 f"Expected 1 launched + 1 queued, got "
  377 | |                 f"[(r1.status={r1.status}), (r2.status={r2.status})]"
  378 | |             )
      | |_____________^
  379 |           finally:
  380 |               JOB_REGISTRY_DOC.pop(test_project.id, None)
      |
  help: Break down assertion into multiple parts
  TC004 Move import `sqlalchemy.orm.sessionmaker` out of type-checking block. Import is used for more than type hinting.
    --> tests/integration/test_doc_indexer.py:21:41
     |
  20 |     from sqlalchemy import Engine
  21 |     from sqlalchemy.orm import Session, sessionmaker
     |                                         ^^^^^^^^^^^^
  22 |
  23 | from orch.db.models import Project, WorkItem, WorkItemType
     |
    ::: tests/integration/test_doc_indexer.py:81:32
     |
  79 |     ) -> None:
  80 |         """Index 3 items with distinct content → 3 work_item_ids in the table."""
  81 |         test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
     |                                ------------ Used at runtime here
  82 |
  83 |         project_id = "test-proj-doc-basic"
     |
  help: Move out of type-checking block
  E501 Line too long (102 > 100)
     --> tests/integration/test_doc_indexer.py:118:101
      |
  116 |                     title="Third item",
  117 |                     type=WorkItemType.Issue,
  118 |                     functional_doc_content="This is the content for the third item about doohickeys.",
      |                                                                                                     ^^
  119 |                     updated_at=now,
  120 |                 ),
      |
  E501 Line too long (103 > 100)
    --> tests/unit/test_qa_engine_classifier.py:34:101
     |
  33 |     @pytest.mark.asyncio
  34 |     async def test_slash_override_history_returns_workitem_aware(self, mock_config: MagicMock) -> None:
     |                                                                                                     ^^^
  35 |         """AC2: /history chip forces workitem_aware pipeline."""
  36 |         from orch.rag.classifier import classify_query
     |
  E501 Line too long (106 > 100)
    --> tests/unit/test_qa_engine_classifier.py:46:101
     |
  45 |     @pytest.mark.asyncio
  46 |     async def test_slash_override_findusages_returns_workitem_aware(self, mock_config: MagicMock) -> None:
     |                                                                                                     ^^^^^^
  47 |         """AC2: /findusages chip forces workitem_aware pipeline."""
  48 |         from orch.rag.classifier import classify_query
     |
  Found 12 errors.
  [*] 2 fixable with the `--fix` option (3 hidden fixes can be enabled with the `--unsafe-fixes` option).
  make: *** [Makefile:17: lint] Error 1
  $ mkdir -p ai-dev/active/F-00062/reports
  (no output)
  ← Write ai-dev/active/F-00062/reports/F-00062_S15_QvGate_report.md
  Wrote file successfully.


## Gate Command

The quality gate that failed runs:
```bash
make lint
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
