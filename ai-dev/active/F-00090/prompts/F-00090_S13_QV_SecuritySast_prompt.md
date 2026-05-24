# F-00090_S13_QV_SECURITY-SAST_prompt

**Work Item**: F-00090 -- Regression-rate tracking
**QV Step**: S13
**Gate**: security-sast

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

- `ai-dev/active/F-00090/reports/F-00090_S13_QualityValidation_report.md` -- QV report

## Context

You are running the **SECURITY-SAST** Quality Validation gate for F-00090.

Run the command, capture full stdout+stderr, report PASS or FAIL.

## Gate Command

```bash
make security-sast
```

## Pass Criteria

Exit code 0 = PASS. Any non-zero exit = FAIL.

## Report

Write `ai-dev/active/F-00090/reports/F-00090_S13_QualityValidation_report.md` with:

- Exact command run
- Exit code
- Relevant stdout/stderr (truncate long traces but include the failure summary)
- Pass/fail verdict

## QV Result Contract

```json
{
  "step": "S13",
  "agent": "qv-gate",
  "work_item": "F-00090",
  "overall_status": "pass|fail",
  "gates": {
    "security-sast": {"status": "pass|fail", "command": "make security-sast", "summary": "", "error_output": ""}
  },
  "failing_gates": [],
  "notes": ""
}
```
