# CR-00079_S03_CodeReview_Final_prompt

**Work Item**: CR-00079 — Generate smaller, single-concern workflow steps in the design-creation skills
**Step**: S03
**Agent**: code-review-final-impl

---

## ⛔ Docker / Migrations

Standard policy — read-only review. Do not run container-mutating commands; do
not apply migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00079 --json`.
- `ai-dev/work/CR-00079/CR-00079_CR_Design.md` — design doc (all ACs).
- `ai-dev/work/CR-00079/reports/CR-00079_S01_Backend_report.md` and `CR-00079_S02_CodeReview_report.md`.
- The full `git diff origin/main` for the item.

## Output Files

- `ai-dev/work/CR-00079/reports/CR-00079_S03_CodeReview_Final_report.md` — review report.

## Context

You are the global cross-step reviewer for CR-00079 — a Markdown-only guidance
change. S02 reviewed S01 per-agent; your job is end-to-end completeness and
consistency.

## Review Checklist

1. **AC1** — all three `iw-new-*` skills carry the step-granularity rule and a concrete, actionable sizing checklist.
2. **AC2** — `skills/iw-workflow/SKILL.md` holds the canonical rule; the three skills reference it; the design templates point to it; the `.claude/skills/**` and `ai-dev/templates/**` copies are byte-identical to their masters (verify with `diff -q`).
3. **AC3** — `git diff origin/main` is confined to Markdown under `skills/`, `.claude/skills/`, `templates/design/`, `ai-dev/templates/` — and to `scope.allowed_paths`. No `orch/`, `dashboard/`, `executor/` file touched. The `workflow-manifest.json` schema is unchanged.
4. **Consistency** — one rule, four files, no divergence; the templates' pointer is accurate and one line.
5. **Self-consistency** — this CR is itself about small steps; confirm the guidance it adds would, if applied, have caught the CR-00076 S01 monolith (a quick sanity check, recorded as a note).
6. **Operator follow-up** — the cross-repo skill-propagation follow-up is recorded.
7. **QV readiness** — a Markdown-only diff must not break `lint` / `unit-tests` / `integration-tests`; if S01/S02 reports suggest otherwise, investigate.

Severities: CRITICAL (any AC unmet / scope breach), HIGH, MEDIUM, LOW.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-final-impl",
  "work_item": "CR-00079",
  "completion_status": "complete",
  "verdict": "pass|fail",
  "ac_status": {"AC1": "pass|fail", "AC2": "pass|fail", "AC3": "pass|fail"},
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "", "detail": ""}],
  "notes": ""
}
```

## Lifecycle Commands

Start: `uv run iw step-start CR-00079 --step S03`
On completion: write the report, then
`uv run iw step-done CR-00079 --step S03 --report ai-dev/work/CR-00079/reports/CR-00079_S03_CodeReview_Final_report.md`
You MUST call `step-done` (with `--report`) before exiting.
