# F-00090_S14_QV_UNIT-TESTS_prompt

**Work Item**: F-00090 -- Regression-rate tracking
**QV Step**: S14
**Gate**: unit-tests

---

## ⛔ Docker is off-limits

Standard policy applies. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

This step does not modify migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00090 --json`.
- `ai-dev/active/F-00090/F-00090_Feature_Design.md` -- Design document
- `Makefile` and `CLAUDE.md` -- gate command source of truth

## Output Files

- `ai-dev/active/F-00090/reports/F-00090_S14_QualityValidation_report.md` -- QV report

## Context

You are running the **UNIT-TESTS** Quality Validation gate for F-00090.

Run the command, capture full stdout+stderr, report PASS or FAIL.

## Gate Command

```bash
make test-unit
```

## Pass Criteria

Exit code 0 = PASS. Any non-zero exit = FAIL.

## Report

Write `ai-dev/active/F-00090/reports/F-00090_S14_QualityValidation_report.md` with:

- Exact command run
- Exit code
- Relevant stdout/stderr (truncate long traces but include the failure summary)
- Pass/fail verdict

## QV Result Contract

```json
{
  "step": "S14",
  "agent": "qv-gate",
  "work_item": "F-00090",
  "overall_status": "pass|fail",
  "gates": {
    "unit-tests": {"status": "pass|fail", "command": "make test-unit", "summary": "", "error_output": ""}
  },
  "failing_gates": [],
  "notes": ""
}
```
