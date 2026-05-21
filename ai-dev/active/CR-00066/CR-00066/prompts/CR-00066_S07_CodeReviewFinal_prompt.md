# CR-00066_S07_CodeReviewFinal_prompt

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Step**: S07
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00066 --json`
- `ai-dev/active/CR-00066/CR-00066_CR_Design.md` — Design document
- `ai-dev/work/CR-00066/reports/CR-00066_S05_CodeReview_report.md`
- `ai-dev/work/CR-00066/reports/CR-00066_S06_CodeReviewFix_report.md`
- All changed files across S01–S06

## Task

Global final review. Verify:

1. All S05 CRITICAL/HIGH/MEDIUM_FIXABLE findings are resolved in S06.
2. **AC coverage** — check each of AC1–AC6 from the design:
   - AC1: seed values present for the 4 known models.
   - AC2: step_monitor correctly sets peak/last.
   - AC3: Context column visible in template.
   - AC4: Color classes applied correctly per threshold.
   - AC5: Completed step shows peak, not current.
   - AC6: NULL context_window_tokens shows raw count only.
3. No new issues introduced by S06 fixes.
4. Migration is clean (3 columns only, seed UPDATE correct).

```bash
make lint && make format-check && make typecheck
```

## Output Files

- `ai-dev/work/CR-00066/reports/CR-00066_S07_CodeReviewFinal_report.md`

## Subagent Result Contract

```bash
uv run iw step-done CR-00066 --step S07 \
  --report ai-dev/work/CR-00066/reports/CR-00066_S07_CodeReviewFinal_report.md
```

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00066",
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
