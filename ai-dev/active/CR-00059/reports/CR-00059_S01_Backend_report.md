# CR-00059 — S01 Backend Report

## Summary

Implemented mutation-testing foundation for `orch/daemon/` scope:

- Added `mutmut>=2.5,<3.0` to dev dependencies in `pyproject.toml` and regenerated `uv.lock`.
- Added `[tool.mutmut]` config block with:
  - `paths_to_mutate = "orch/daemon/"`
  - `tests_dir = "tests/"`
  - runner scoped to `tests/unit/daemon/ tests/integration/daemon/ -x --tb=no -q`
- Added four Makefile targets and `.PHONY` entries:
  - `mutation-check`
  - `mutation-audit`
  - `mutation-results`
  - `mutation-show`
- Added RED-first guard test file `tests/unit/test_mutmut_setup.py` with 2 tests pinning config + Makefile targets.
- Updated docs and plan:
  - `docs/IW_AI_Core_Testing_Strategy.md` (§5/§8/§9)
  - `ai-dev/work/TESTS_ENHANCEMENT.md` (§5 follow-up row, §6 item 2.1 status, §11 changelog)

## RED → GREEN evidence

- RED run (`uv run pytest tests/unit/test_mutmut_setup.py -v`) failed as expected before implementation:
  - `test_makefile_exposes_four_mutation_targets`: `No rule to make target 'mutation-check'`
  - `test_pyproject_tool_mutmut_block_pins_orch_daemon_target`: `[tool.mutmut] block missing`
- GREEN run after implementation:
  - `PYTEST_ADDOPTS='--no-cov' uv run pytest tests/unit/test_mutmut_setup.py -v` → `2 passed`

## Spike measurement table (deliverable)

CR-00059 — Mutation testing spike (P2-CR-A)
Date: 2026-05-18
Scope: orch/daemon/ (audit via `make mutation-audit`)

| Metric                          | Value           |
|---------------------------------|-----------------|
| Total mutants generated         | 0               |
| Killed                          | 0               |
| Survived                        | 0               |
| Timeout                         | 0               |
| Suspicious                      | 0               |
| Mutation score (K / (K+S) × 100)| 0.00%           |
| Wall-clock (total)              | 0:17:17         |
| Modules covered                 | 25 of 25        |

Modules covered:

- orch/daemon/__main__.py
- orch/daemon/auto_merge.py
- orch/daemon/auto_merge_health.py
- orch/daemon/batch_manager.py
- orch/daemon/batch_merge_hooks.py
- orch/daemon/browser_env.py
- orch/daemon/chat_summarization_poller.py
- orch/daemon/container_info.py
- orch/daemon/doc_index_poller.py
- orch/daemon/doc_job_poller.py
- orch/daemon/execution_report.py
- orch/daemon/fix_cycle.py
- orch/daemon/keep_alive_poller.py
- orch/daemon/main.py
- orch/daemon/merge_queue.py
- orch/daemon/migration_pipeline.py
- orch/daemon/migration_rebase.py
- orch/daemon/project_registry.py
- orch/daemon/qv_baseline.py
- orch/daemon/review_mapping.py
- orch/daemon/scope_overlap.py
- orch/daemon/state_machine.py
- orch/daemon/step_monitor.py
- orch/daemon/worktree_compose.py
- orch/daemon/worktree_reaper.py

Top 5 surviving mutants:

- None captured (mutant generation was blocked by coverage gate before execution)

Infrastructure blockers encountered:

- Every module-level mutmut run exited through pytest coverage gating before mutant execution:
  - `FAIL Required test coverage of 50.0% not reached. Total coverage: 12.28%`
- No live-DB guard propagation failures observed.
- No FTS-trigger/testcontainer misfire signatures observed.

Canonical artifact: `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt`

## Verification run summary

- `python -c "import tomllib; ... ['tool']['mutmut']"` parses and prints expected block.
- `make -n mutation-check MODULE=orch/daemon/auto_merge.py` parses.
- `make -n mutation-audit` parses.
- `make -n mutation-results` parses.
- `make -n mutation-show ID=1` parses.
- `uv run mutmut version` prints `mutmut version 2.5.1`.

## Notes

- This step intentionally does **not** wire mutation testing into `make quality`, `make check`, daemon QV gates, or GitHub workflows.
- Follow-up row `P2-CR-A-followup-mutation-block` was added to the plan for widening scope and defining blocking gate behavior after runner handling.
