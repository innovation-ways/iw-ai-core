# I-00105_S04_CodeReview_prompt

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S04
**Agent**: code-review-impl
**Step Being Reviewed**: S03 (backend-impl — effective-budget meter)

---

## ⛔ Docker / Migrations

Standard policy — read-only review. Do not run container-mutating commands; do
not apply migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00105 --json`.
- `ai-dev/work/I-00105/I-00105_Issue_Design.md` — design doc (AC1, §Root Cause).
- `ai-dev/work/I-00105/reports/I-00105_S03_Backend_report.md` — S03 report.
- Every file in S03's `files_changed` — `orch/chat/context_usage.py` and the new test.
- `docs/research/R-00078-agent-tool-output-context-capping.md` — the effective-budget formula.

## Output Files

- `ai-dev/work/I-00105/reports/I-00105_S04_CodeReview_report.md` — review report.

## Review Checklist

Verify and record a finding (with severity) for each:

1. **Formula correctness** — usage is computed against `context_window − max_output_tokens − safety_buffer`, not the raw window. The percentage can reach/exceed 100% when input is past the effective ceiling (AC1).
2. **NULL handling** — `max_output_tokens is None` falls back to raw-window behaviour and never raises (design Notes).
3. **Purity** — the computation function stays pure (no DB call inside it); row resolution is a separate thin function.
4. **Reproduction test** — `test_i_00105_context_pct_accounts_for_output_reservation` exists, is behavioural (asserts `pct >= 100.0`, not shape), and would genuinely fail against pre-fix raw-window logic. The S03 report's `tdd_red_evidence` shows a real RED line.
5. **No regression** — existing `compute_context_pct` callers still work (the old function kept, or every caller updated within scope).
6. **Scope** — `git diff` is confined to `scope.allowed_paths`; no production-policy violation.
7. **Pre-flight** — S03's report shows `format`/`typecheck`/`lint` and `test-assertions` green.

Severities: CRITICAL (AC not met / scope breach), HIGH (correctness gap), MEDIUM (weak test / style), LOW (nit). A CRITICAL or HIGH finding means the step does not pass review.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00105",
  "step_reviewed": "S03",
  "completion_status": "complete",
  "verdict": "pass|fail",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "", "detail": ""}],
  "notes": ""
}
```

## Lifecycle Commands

Start: `uv run iw step-start I-00105 --step S04`
On completion: write the report, then
`uv run iw step-done I-00105 --step S04 --report ai-dev/work/I-00105/reports/I-00105_S04_CodeReview_report.md`
You MUST call `step-done` (with `--report`) before exiting.
