# CR-00079_S02_CodeReview_prompt

**Work Item**: CR-00079 — Generate smaller, single-concern workflow steps in the design-creation skills
**Step**: S02
**Agent**: code-review-impl
**Step Being Reviewed**: S01 (backend-impl — skills + templates edit)

---

## ⛔ Docker / Migrations

Standard policy — read-only review. Do not run container-mutating commands; do
not apply migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00079 --json`.
- `ai-dev/work/CR-00079/CR-00079_CR_Design.md` — design doc (Current/Desired Behavior, AC1–AC3).
- `ai-dev/work/CR-00079/reports/CR-00079_S01_Backend_report.md` — S01 report.
- Every file in S01's `files_changed` — the four `SKILL.md` files, the templates, and the synced copies.

## Output Files

- `ai-dev/work/CR-00079/reports/CR-00079_S02_CodeReview_report.md` — review report.

## Review Checklist

Verify and record a finding (with severity) for each:

1. **AC1** — `skills/iw-new-feature/SKILL.md`, `skills/iw-new-incident/SKILL.md`, and `skills/iw-new-cr/SKILL.md` each carry the step-granularity rule AND a step-sizing checklist. The wording is **concrete and actionable** (specific "split it" triggers), not a vague platitude like "keep steps small". A vague, unactionable addition is a HIGH finding.
2. **AC2 — canonical rule** — `skills/iw-workflow/SKILL.md` states the canonical step-granularity rule; the three `iw-new-*` skills reference it rather than each inventing divergent wording.
3. **AC2 — templates** — the design templates under `templates/design/` point to the rule in their Agents-and-Execution-Order section (one line, not bloat).
4. **AC2 — sync** — `.claude/skills/iw-new-feature|iw-new-incident|iw-new-cr|iw-workflow/SKILL.md` are byte-identical to their `skills/` masters, and `ai-dev/templates/` matches `templates/design/`. Run `diff -q` yourself to confirm.
5. **AC3 — scope** — `git diff origin/main` touches ONLY Markdown under `skills/`, `.claude/skills/`, `templates/design/`, `ai-dev/templates/`. No `orch/`, `dashboard/`, `executor/` file modified. No manifest-schema change.
6. **Consistency** — the rule is phrased consistently across all four skills (same substance; per-item-type phrasing is fine).
7. **Operator follow-up** — the S01 report flags cross-repo (IW-AI-DEV / InnoForge) skill propagation as an operator follow-up.
8. **Pre-flight** — S01's report shows `format` and `lint` green.

Severities: CRITICAL (AC not met / scope breach), HIGH (vague/unactionable guidance, divergent wording, sync mismatch), MEDIUM (style / minor inconsistency), LOW (nit). A CRITICAL or HIGH finding means the step does not pass review.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00079",
  "step_reviewed": "S01",
  "completion_status": "complete",
  "verdict": "pass|fail",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "", "detail": ""}],
  "notes": ""
}
```

## Lifecycle Commands

Start: `uv run iw step-start CR-00079 --step S02`
On completion: write the report, then
`uv run iw step-done CR-00079 --step S02 --report ai-dev/work/CR-00079/reports/CR-00079_S02_CodeReview_report.md`
You MUST call `step-done` (with `--report`) before exiting.
