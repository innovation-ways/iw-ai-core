# I-00105_S11_CodeReview_Final_prompt

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S11
**Agent**: code-review-final-impl

---

## ⛔ Docker / Migrations

Standard policy. You may run the full test suites (they use testcontainers).
Do not run container-mutating commands; do not apply migrations to the live DB.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00105 --json`.
- `ai-dev/work/I-00105/I-00105_Issue_Design.md` — design doc (all ACs).
- All step reports `ai-dev/work/I-00105/reports/I-00105_S01..S10_*_report.md`.
- The full `git diff origin/main` for the item.
- `docs/research/R-00078-agent-tool-output-context-capping.md`.

## Output Files

- `ai-dev/work/I-00105/reports/I-00105_S11_CodeReview_Final_report.md` — review report.

## Context

You are the global cross-step reviewer for I-00105. Per-agent reviews
(S04/S06/S08/S10) checked each step in isolation; your job is end-to-end
correctness, integration consistency, and completeness.

## Review Checklist

1. **AC1 — effective-budget meter end-to-end.** The migration (`max_output_tokens`), the meter (`context_usage.py`), and both dashboard gauges form one consistent path: a MiniMax-M2.7-class step at ~131K input reports near/over 100%, not ~64%.
2. **AC2 — cap + spill.** Oversized tool output is spilled to a file with a recoverable preview+path; no in-place truncation-without-spill anywhere.
3. **AC3 — tests.** The reproduction test fails pre-fix / passes post-fix; regression tests cover meter + migration + cap + overflow-detection helper and assert semantic values.
4. **AC4 — clean failure on overflow.** The executor detects a context-window-overflow signature and, when the step has not completed cleanly, finalizes it as a clearly-attributed `step-fail` with a blocker naming the overflow — it does not let the step limp on in a degraded state. The detection signatures are unit-tested. A clean `step-done` is never overridden.
5. **Consistency** — the effective-budget formula is defined once and reused (S03 meter ↔ S07 compaction threshold); they do not diverge. The safety-buffer / config vars are single-sourced in `orch/config.py`.
6. **Scope integrity** — `git diff origin/main` is confined to `scope.allowed_paths`; no file under `orch/`, `dashboard/`, `executor/` outside the allow-list; exactly one new migration file under `orch/db/migrations/versions/`.
7. **`make migration-check`** still passes (re-run it).
8. **Full suites** — run `make test-unit` and `make test-integration`; a failure traceable to I-00105's changes is CRITICAL.
9. **No production-policy violation** — no docker-mutating commands, no live-DB migration calls, no hardcoded ports/paths/credentials.

Severities: CRITICAL (any AC unmet / suite failure / scope breach), HIGH, MEDIUM, LOW.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "code-review-final-impl",
  "work_item": "I-00105",
  "completion_status": "complete",
  "verdict": "pass|fail",
  "ac_status": {"AC1": "pass|fail", "AC2": "pass|fail", "AC3": "pass|fail", "AC4": "pass|fail"},
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "", "detail": ""}],
  "suite_results": {"unit": "pass|fail", "integration": "pass|fail", "migration-check": "pass|fail"},
  "notes": ""
}
```

## Lifecycle Commands

Start: `uv run iw step-start I-00105 --step S11`
On completion: write the report, then
`uv run iw step-done I-00105 --step S11 --report ai-dev/work/I-00105/reports/I-00105_S11_CodeReview_Final_report.md`
You MUST call `step-done` (with `--report`) before exiting.
