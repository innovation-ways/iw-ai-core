# I-00105_S08_CodeReview_prompt

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S08
**Agent**: code-review-impl
**Step Being Reviewed**: S07 (backend-impl — executor tool-output cap + compaction calibration)

---

## ⛔ Docker / Migrations

Standard policy — read-only review. Do not run container-mutating commands; do
not apply migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00105 --json`.
- `ai-dev/work/I-00105/I-00105_Issue_Design.md` — design doc (AC2 & AC4, §Root Cause causes 2, 3 & 4).
- `ai-dev/work/I-00105/reports/I-00105_S07_Backend_report.md` — S07 report.
- Every file in S07's `files_changed` — `executor/`, `orch/config.py`, tests.
- `docs/research/R-00078-agent-tool-output-context-capping.md` — the cap+spill recommendation and the forbidden anti-pattern.

## Output Files

- `ai-dev/work/I-00105/reports/I-00105_S08_CodeReview_report.md` — review report.

## Review Checklist

Verify and record a finding (with severity) for each:

1. **Cap + spill (AC2)** — oversized tool output is written **in full** to a file under the step work directory, and the agent receives a head+tail preview **plus the file path** (recoverable). An in-place head/tail snippet with an inline `…truncated…` marker and NO spill file is a CRITICAL finding (R-00078 / Codex #14206: "preserves neither exactness nor recoverability").
2. **Under-cap passthrough** — results below the cap are returned byte-for-byte unchanged.
3. **Config-driven** — the cap byte budget, safety buffer, and compaction-threshold fraction live in `orch/config.py` as `IW_CORE_*` vars with safe documented defaults; nothing hardcoded (`CLAUDE.md` rule).
4. **Compaction calibration** — the proactive-compaction trigger is calibrated to ~75% of the *effective* budget (`window − max_output − buffer`), consistent with S03's formula — not a second divergent formula, not the raw window. Where a runtime's threshold is not controllable, the report says so honestly.
5. **Overflow detection → clean step-fail (AC4)** — the executor detects a context-window-overflow signature in the runtime output and, when the step did not complete cleanly, finalizes it as a clearly-attributed `step-fail` with a blocker naming the overflow. A non-completed overflowed step left to limp on, or handled only as a generic stall/timeout, is a CRITICAL finding. The detection signatures live in a unit-testable helper; a clean `step-done` is never overridden.
6. **No prohibited commands** — the executor code does not kill/restart/remove containers; no live-DB migration calls.
7. **Tests** — if a cap/spill helper was extracted, tests assert the spill file holds the full original content and the preview carries head+tail+path; the overflow-detection helper has tests asserting an overflow signature is detected (clear blocker message) and clean output is not. If a surface is pure shell, the report explains the testable surface.
8. **Scope** — `git diff` confined to `scope.allowed_paths`.

Severities: CRITICAL (AC not met / anti-pattern / scope breach), HIGH (correctness gap), MEDIUM (weak test / style), LOW (nit). A CRITICAL or HIGH finding means the step does not pass review.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "I-00105",
  "step_reviewed": "S07",
  "completion_status": "complete",
  "verdict": "pass|fail",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "", "detail": ""}],
  "notes": ""
}
```

## Lifecycle Commands

Start: `uv run iw step-start I-00105 --step S08`
On completion: write the report, then
`uv run iw step-done I-00105 --step S08 --report ai-dev/work/I-00105/reports/I-00105_S08_CodeReview_report.md`
You MUST call `step-done` (with `--report`) before exiting.
