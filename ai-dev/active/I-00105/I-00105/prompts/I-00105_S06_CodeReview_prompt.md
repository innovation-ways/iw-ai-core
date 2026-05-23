# I-00105_S06_CodeReview_prompt

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S06
**Agent**: code-review-impl
**Step Being Reviewed**: S05 (frontend-impl — dashboard context gauge)

---

## ⛔ Docker / Migrations

Standard policy — read-only review. Do not run container-mutating commands; do
not apply migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00105 --json`.
- `ai-dev/work/I-00105/I-00105_Issue_Design.md` — design doc (AC1).
- `ai-dev/work/I-00105/reports/I-00105_S05_Frontend_report.md` — S05 report.
- `ai-dev/work/I-00105/reports/I-00105_S03_Backend_report.md` — S03 report (the meter S05 wires to).
- Every file in S05's `files_changed`.

## Output Files

- `ai-dev/work/I-00105/reports/I-00105_S06_CodeReview_report.md` — review report.

## Review Checklist

Verify and record a finding (with severity) for each:

1. **Per-step gauge** — the percentage now comes from S03's effective-budget meter, computed in `dashboard/routers/items.py`; **no raw-window division (`ctx_peak / ctx_window`) remains in `item_steps_table.html`**. The `items.py` lookup resolves `max_output_tokens` per step. A near-ceiling step renders near/over 100%, not ~64%, and the displayed label is not clamped to 100.
2. **Chat gauge consistency** — `dashboard/routers/chat.py` / `chat.js` either use the effective-budget meter, or already delegate to the shared helper S03 fixed (the S05 report must state which). The two gauges must not diverge.
3. **NULL fallback** — a runtime with NULL `max_output_tokens` renders as today (raw window); no template special-casing.
4. **Tests** — `tests/dashboard/` tests assert the **specific rendered percentage** (≥100% for the MiniMax-M2.7-like case; raw-window % for the NULL case), not just that a gauge element exists.
5. **Jinja2 / lint** — `format`-filter calls are `%`-style (not `str.format`-style); `make lint` (JS `node --check` + template check) is green per the S05 report.
6. **Scope** — `git diff` confined to `scope.allowed_paths`.

Severities: CRITICAL (AC not met / scope breach), HIGH (correctness gap), MEDIUM (weak test / style), LOW (nit). A CRITICAL or HIGH finding means the step does not pass review.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00105",
  "step_reviewed": "S05",
  "completion_status": "complete",
  "verdict": "pass|fail",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "", "detail": ""}],
  "notes": ""
}
```

## Lifecycle Commands

Start: `uv run iw step-start I-00105 --step S06`
On completion: write the report, then
`uv run iw step-done I-00105 --step S06 --report ai-dev/work/I-00105/reports/I-00105_S06_CodeReview_report.md`
You MUST call `step-done` (with `--report`) before exiting.
