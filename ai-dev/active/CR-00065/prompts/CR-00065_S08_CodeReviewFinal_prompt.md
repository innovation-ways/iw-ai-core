# CR-00065_S08_CodeReviewFinal_prompt

**Work Item**: CR-00065 — Live Agent Session Log Viewer
**Step**: S08
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00065 --json`
- `ai-dev/active/CR-00065/CR-00065_CR_Design.md` — Design document
- `ai-dev/work/CR-00065/reports/CR-00065_S06_CodeReview_report.md` — Initial review
- `ai-dev/work/CR-00065/reports/CR-00065_S07_CodeReviewFix_report.md` — Fix report
- All changed files across S01–S07

## Task

Global cross-agent final review. Verify:

1. **All S06 CRITICAL/HIGH/MEDIUM_FIXABLE findings are resolved** — check each finding against S07's `findings_fixed` list.
2. **Integration correctness** — the `session_reader` module is correctly imported and used by the API endpoint; the API endpoint template context matches what the Jinja2 template expects; `step_monitor` stores the session file in the correct DB column.
3. **AC coverage** — verify each acceptance criterion (AC1–AC6) in the design is satisfied by the implementation.
4. **No new issues introduced by S07 fixes**.
5. **Migration is clean** — only the `session_file` column, no drift.

Run:

```bash
make lint
make format-check
make typecheck
```

## Output Files

- `ai-dev/work/CR-00065/reports/CR-00065_S08_CodeReviewFinal_report.md`

## Subagent Result Contract

```bash
uv run iw step-done CR-00065 --step S08 \
  --report ai-dev/work/CR-00065/reports/CR-00065_S08_CodeReviewFinal_report.md
```

```json
{
  "step": "S08",
  "agent": "code-review-final-impl",
  "work_item": "CR-00065",
  "verdict": "pass|fail",
  "all_prior_findings_resolved": true,
  "ac_coverage": {
    "AC1": "satisfied|partial|missing",
    "AC2": "satisfied|partial|missing",
    "AC3": "satisfied|partial|missing",
    "AC4": "satisfied|partial|missing",
    "AC5": "satisfied|partial|missing",
    "AC6": "satisfied|partial|missing"
  },
  "new_findings": [],
  "mandatory_fix_count": 0,
  "notes": ""
}
```
