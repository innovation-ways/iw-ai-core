# I-00088_S05_CodeReview_Final_prompt

**Work Item**: I-00088 — Auto-merge health probe always fails — CLI-shape mismatch with step_executor.sh
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Same policy as the implementation steps. Read-only `docker ps` / `inspect` /
`logs` is OK. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this work item.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00088 --json`
- `ai-dev/active/I-00088/I-00088_Issue_Design.md` — Design document
- `ai-dev/work/I-00088/reports/I-00088_S01_Backend_report.md`
- `ai-dev/work/I-00088/reports/I-00088_S02_CodeReview_report.md`
- `ai-dev/work/I-00088/reports/I-00088_S03_Tests_report.md`
- `ai-dev/work/I-00088/reports/I-00088_S04_CodeReview_report.md`
- All files in S01 and S03's `files_changed`

## Output Files

- `ai-dev/work/I-00088/reports/I-00088_S05_CodeReview_Final_report.md`

## Context

You are performing the final cross-agent review of all I-00088 work. The
per-step reviews verified each step in isolation; your job is to verify
the **integration** between the fix and the tests, and the **completeness**
against the design's acceptance criteria.

## Read the Design Document FIRST

- `## Acceptance Criteria` — three criteria (AC1, AC2, AC3). Every one is a
  mandatory check.
- `## TDD Approach` — names two test files. Both MUST appear in some
  implementation report's `files_changed`. Missing → CRITICAL.
- `## Notes` — the post-merge chip-lag caveat. Confirm the implementation
  did NOT add a workaround for it (the design explicitly punts the
  historical-event cleanup to operator hygiene).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

New violations in changed files are CRITICAL.

## Review Checklist

### 1. Completeness vs Design Document

- AC1 (bug is fixed): the probe in `orch/daemon/auto_merge_health.py` now
  invokes `bash step_executor_lib.sh auto_merge_resolve <cli_tool> <model>` —
  mirroring `orch/daemon/auto_merge.py:717-736`, NOT shelling out to
  `step_executor.sh` (the buggy original) and NOT shelling out directly to
  `opencode` / `claude` (which would break probe-resolver parity). Verify
  by reading the post-S01 file.
- AC2 (regression test exists): `tests/integration/test_auto_merge_health_runtime.py`
  exists, uses a fake `opencode` (or `claude`) shim on `PATH`, runs through
  the real `step_executor_lib.sh`, and asserts on capture-file contents
  (both the model name and the prompt string).
- AC3 (unit tests assert on argv shape): every mocked-subprocess test in
  `tests/unit/test_auto_merge_health.py` has assertions on `run.call_args.args[0]`
  covering `argv[1].endswith("step_executor_lib.sh")`,
  `argv[2] == "auto_merge_resolve"`, `argv[3] == resolved.cli_tool`, and
  `argv[4] == resolved.model`.
- Scope: the only files modified should be
  `orch/daemon/auto_merge_health.py`,
  `tests/unit/test_auto_merge_health.py`,
  `tests/integration/test_auto_merge_health_runtime.py`.
  Any other modified file is a CRITICAL scope violation (cross-check against
  `workflow-manifest.json:scope.allowed_paths`). Specifically: any change
  under `executor/` is a CRITICAL violation.

### 2. Cross-Agent Consistency

- Does the unit test's argv assertion match the actual argv shape the
  Backend produced? Read both files and compare — they MUST agree on
  `argv[1]` ending in `step_executor_lib.sh`, on `argv[2] == "auto_merge_resolve"`,
  on the positions of `cli_tool` and `model`, and on the stdin contract
  (`input=PROBE_PROMPT`).
- Does the integration test's fake-CLI assertion match the same shape?
  All three layers must agree: backend produces argv X; unit test asserts
  argv X; integration test's fake CLI (via real lib-script dispatch) sees
  the runtime invocation produced by `_run_agent_oneshot` against argv X.
- If unit and integration tests disagree on what argv shape they expect,
  that is a CRITICAL inconsistency finding.
- Does the probe's pattern match `orch/daemon/auto_merge.py:717-736`?
  Open both files and compare side-by-side. The intent of the redrafted
  design is that the probe and the resolver share the same invocation
  pattern so they cannot drift. Any meaningful divergence (different argv
  order, different env vars beyond the documented PATH deviation, different
  flags) is a HIGH finding.

### 3. Integration Points

- `orch/auto_merge_aggregator.py::get_health_summary` reads `runtime_reachable`
  from `event_metadata`. Confirm the post-fix probe still writes this key
  with the same type (`bool`). Mismatched type → CRITICAL.
- The chip template (`dashboard/templates/fragments/auto_merge_status_chip.html`)
  reads `health_state` (computed from `runtime_reachable` + failure count).
  No change to that contract; if the post-fix probe stops writing the key
  the chip silently misclassifies. Verify the key is still there.

### 4. Test Coverage (Holistic)

- Are BOTH success and failure paths covered in the integration test? (Fake
  CLI returning `OK` AND fake CLI exiting non-zero.)
- Is the timeout path still covered at the unit level?
- Is the phase-0 skip path still covered at the unit level?
- Is the "recent probe" skip path still covered at the unit level?
- If any pre-existing behaviour is no longer covered, raise a HIGH finding.

### 5. Architecture Compliance

- Read `orch/CLAUDE.md`. The probe must remain a non-blocking, best-effort
  subprocess. The fix must not introduce blocking I/O, threading, or async.
- Read `executor/CLAUDE.md`. The probe should NOT call `step_executor.sh`
  any more. If any code path still imports or references `step_executor.sh`
  from `auto_merge_health.py`, that is a CRITICAL finding.
- The probe SHOULD call `step_executor_lib.sh` (in `auto_merge_resolve` mode)
  — that's the canonical pattern that `auto_merge.py` uses. If
  `step_executor_lib.sh` is NOT referenced from `auto_merge_health.py`, that
  is a CRITICAL finding (the design's central property of probe-resolver
  parity has been violated).

### 6. Security (Cross-Cutting)

- Subprocess argv must be built from values that originate in
  `projects.toml` + per-project DB config, not from any HTTP input. Trace
  the path from `resolve_project_config` back to its sources and confirm.
- No `shell=True`. The argv must be a list.

## Test Verification (NON-NEGOTIABLE)

Run the focused test suite — the files this work item modified:

```bash
uv run pytest tests/unit/test_auto_merge_health.py tests/integration/test_auto_merge_health_runtime.py -v --no-cov
```

If any test fails, that is a CRITICAL finding. Capture the summary line in
`test_summary`. Do NOT run `make test-unit` or `make allure-integration`
here — the QV gates (S09 unit-tests, S10 integration-tests) own full-suite
execution, and duplicating them in this step burns wall-clock budget for no
new signal (see I-00073/S03 post-mortem; convention confirmed against
I-00087/S05).

## Severity Levels

Standard scale. `verdict: pass` requires zero CRITICAL/HIGH/MEDIUM_FIXABLE.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00088",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
