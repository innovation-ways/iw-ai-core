# F-00078_S09_Tests_prompt

**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Step**: S09
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

See S01 prompt. Same rules apply.

## Input Files

- `uv run iw item-status F-00078 --json`
- `ai-dev/active/F-00078/F-00078_Feature_Design.md` -- Especially "Acceptance Criteria", "Boundary Behavior", "Invariants", "TDD Approach"
- All previous step reports in `ai-dev/work/F-00078/reports/`
- `tests/CLAUDE.md` -- Test conventions, fixtures, testcontainer rules
- `tests/conftest.py` -- Existing fixtures (especially the testcontainer + FTS function/trigger fixtures)
- All files modified by S01, S03, S05, S07

## Output Files

- `ai-dev/work/F-00078/reports/F-00078_S09_Tests_report.md` -- Step report
- New: `tests/unit/test_self_assess.py` (extend if S03 already created it; do not duplicate)
- New: `tests/integration/test_project_registry_self_assess.py`
- New: `tests/integration/test_batch_manager_self_assess.py` (extend if S03 already created it)
- New: `tests/dashboard/test_execution_report_self_assess.py` (extend if S05 already created it)
- New: `tests/unit/test_skill_files.py` (extend if S07 already created it)
- New: `tests/integration/test_step_done_analysis_json.py`

## Context

You are filling out the test coverage for F-00078. Earlier steps wrote minimum-viable tests; your job is to ensure every Acceptance Criterion, every Boundary Behavior row, and every Invariant from the design doc is exercised by at least one test.

**Critical**: do NOT duplicate tests already written by S01/S03/S05/S07. First, list what's already covered (read the existing test files), then fill gaps. Your report should explicitly enumerate which AC / Boundary Behavior / Invariant maps to which test.

Read `tests/CLAUDE.md` for the project's test conventions:
- Use testcontainers for integration tests, NOT the live DB.
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` must run after `Base.metadata.create_all()`.
- Replace psycopg2 URLs in testcontainers: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- `monkeypatch.delenv()` for env-var manipulation; never `importlib.reload(orch.config)`.

## Requirements

### 1. Coverage matrix

Build (in your report) a table mapping AC/Boundary/Invariant to test:

| Item | Test |
|------|------|
| AC1: projects.toml flag round-trip | `tests/integration/test_project_registry_self_assess.py::test_flag_true_roundtrips` |
| AC1: flag absent → default False | `tests/integration/test_project_registry_self_assess.py::test_flag_absent_defaults_false` |
| AC2: design skills inject step | `tests/unit/test_skill_files.py::test_design_skills_document_self_assess_injection` (verify SKILL body mentions the conditional injection — full e2e of skill execution is out of scope for pytest) |
| AC3: daemon treats failure as soft | `tests/integration/test_batch_manager_self_assess.py::test_self_assess_failure_does_not_block_merge` |
| AC4: report shows section when findings exist | `tests/dashboard/test_execution_report_self_assess.py::test_section_renders_with_findings` |
| AC5: report hides section when not applicable | `tests/dashboard/test_execution_report_self_assess.py::test_section_absent_when_no_step_or_no_file` |
| AC6: skill output contract | `tests/unit/test_skill_files.py::test_skill_documents_two_file_output_contract` |
| AC7: step-done --analysis-json | `tests/integration/test_step_done_analysis_json.py::test_flag_accepted_for_self_assess` and `::test_flag_rejected_for_other_step_types` |
| Boundary: non-bool projects.toml value | `tests/integration/test_project_registry_self_assess.py::test_non_bool_value_warns_and_defaults_false` |
| Boundary: findings JSON missing | `tests/dashboard/test_execution_report_self_assess.py::test_section_absent_when_findings_file_missing` |
| Boundary: findings JSON malformed | `tests/dashboard/test_execution_report_self_assess.py::test_section_renders_narrative_when_json_malformed` |
| Boundary: all findings target=iw-ai-core | `tests/dashboard/test_execution_report_self_assess.py::test_only_iw_ai_core_subsection_when_no_project_findings` |
| Boundary: all findings target=project | `tests/dashboard/test_execution_report_self_assess.py::test_only_project_subsection_when_no_iw_ai_core_findings` |
| Boundary: self_assess fails with non-zero | `tests/integration/test_batch_manager_self_assess.py::test_failed_self_assess_renders_with_partial_data` |
| Invariant 1: never blocks merge | (covered by AC3) |
| Invariant 2: zero DOM nodes when not applicable | `tests/dashboard/test_execution_report_self_assess.py::test_no_self_assess_html_when_section_absent` |
| Invariant 3: canonical sidecar path | `tests/unit/test_self_assess.py::test_findings_path_for_canonical_form` |
| Invariant 4: skill never writes outside reports dir | `tests/unit/test_skill_files.py::test_skill_constraints_mention_no_outside_writes` (verify skill body says it; runtime enforcement is the executor's worktree sandbox) |
| Invariant 5: target field strict validation | `tests/unit/test_self_assess.py::test_parser_rejects_unknown_target` |
| Invariant 6: deterministic skill injection | (covered by AC2) |

### 2. Specific test gaps to fill

Based on the matrix, ensure these tests exist (write them if missing, extend if S01/S03/S05/S07 created stubs):

**Unit (`tests/unit/test_self_assess.py`)**:
- Parser happy path (full fixture).
- Parser rejects malformed JSON → `SelfAssessParseError`.
- Parser rejects unknown `target` value.
- Parser rejects missing `severity` / `recommendation` / `paste_prompt`.
- Parser tolerates unknown extra fields (forward-compatible).
- `findings_path_for("/x/y/F-00001_self_assess_report.md") == Path("/x/y/F-00001_self_assess_findings.json")`.
- `is_self_assess_step` accepts both StepType enum and string.
- `is_soft_step_failure` matrix: (self_assess, failed) → True; (self_assess, completed) → False; (implementation, failed) → False; (browser_verification, failed) → False.

**Integration — projects.toml**:
- Write a tmp `projects.toml` with `self_assess = true` and assert `ProjectRegistry.load()` returns `self_assess_enabled=True`.
- Same with `self_assess = false` → `False`.
- Without the field → `False`.
- With non-bool (`self_assess = "true"`, `self_assess = 1`, `self_assess = "yes"`) → `False` + WARNING log captured by `caplog`.

**Integration — batch_manager soft-step**:
- Seed a work item with steps S01..S03 all completed and a self_assess step with `RunStatus.failed`.
- Trigger the batch_manager progression logic.
- Assert the batch_item transitions to `merging` (or `completed`, depending on where the next handoff is).
- Assert no `FixCycle` row was created for the self_assess step.
- Negative: same setup but step_type=implementation with `RunStatus.failed` → batch_item does NOT progress to merging (regression guard for "soft-step branching too broad").

**Integration — step-done flag**:
- `iw step-done <ID> S<NN> --report <path.md> --analysis-json <path.json>` succeeds for a self_assess step.
- Same command on an `implementation` step raises `click.UsageError`.
- The CLI persists the report path; the dashboard later resolves the findings JSON via `findings_path_for`.

**Dashboard render**:
- Use `TestClient` against the FastAPI app.
- Seed a Project + WorkItem + WorkflowSteps including a self_assess step + StepRun with `report_file` set.
- Write a real findings JSON file to disk under the per-item reports dir.
- Fetch `/project/<id>/item/<id>/tab/execution-report` and assert the response HTML contains "Self-Assessment".
- Negative: when no self_assess step exists, the response HTML does NOT contain "Self-Assessment".
- Negative: when the step exists but the file is missing, response is 200 (NOT 500), section absent.
- Malformed JSON: response 200, narrative renders, finding list empty.
- Verify XSS escaping: a finding with `paste_prompt` containing `</script><script>alert(1)</script>` round-trips as escaped HTML in the rendered output.

**Skill files** (already partially covered by S07's tests):
- Frontmatter checks (no allowed-tools, no argument-hint, no $ARGUMENTS in body).
- Output contract documented (mentions `_self_assess_report.md` and `_self_assess_findings.json`).
- Each design skill mentions the conditional injection.
- `.claude/skills/` synced copies match masters.

### 3. Coverage threshold

If `pytest-cov` is configured for this project (check Makefile), assert the coverage on `orch/self_assess.py` is ≥ 90% line coverage. Document the actual percentage in your report.

### 4. Do NOT touch

- Production code in `orch/`, `dashboard/`, `skills/`, `templates/design/` — that's already done. If you find a bug while writing tests, raise a `blocker` and let S11 (final review) decide whether to flag it as a fix-cycle issue.
- Existing tests for unrelated functionality.

## Project Conventions

Read `tests/CLAUDE.md` for:
- Testcontainer setup (psycopg URL replacement, FTS function/trigger application).
- Fixture organization (unit vs integration vs dashboard).
- Naming: `test_<thing_under_test>` and class names in PascalCase if used.
- DO NOT mock the DB in integration tests.
- DO NOT call `importlib.reload(orch.config)`; use `monkeypatch.delenv()`.

## TDD Requirement

This step IS the test step. The flow is:

1. Read the existing test files; identify gaps.
2. For each missing test, write the test FIRST (it should pass against existing code if S01/S03/S05/S07 did their job correctly — that's the "GREEN out of the box" case).
3. If a test fails because of a real production bug, raise a `blocker` rather than fixing the production code. Final review (S11) will route the fix.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

Both must pass. Note any test that requires the testcontainer; if the testcontainer fixture isn't present in your worktree, raise a blocker.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "tests-impl",
  "work_item": "F-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_self_assess.py",
    "tests/integration/test_project_registry_self_assess.py",
    "tests/integration/test_batch_manager_self_assess.py",
    "tests/integration/test_step_done_analysis_json.py",
    "tests/dashboard/test_execution_report_self_assess.py",
    "tests/unit/test_skill_files.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed; orch/self_assess.py coverage: <pct>%",
  "blockers": [],
  "notes": "Include the AC↔test coverage matrix in this report."
}
```
