# I-00084_S14_SelfAssess_prompt

**Work Item**: I-00084 — Stale origin/main ref breaks make diff-coverage
**Step**: S14
**Agent**: self-assess-impl

---

## Input Files

- `ai-dev/active/I-00084/I-00084_Issue_Design.md`
- All S01..S13 reports
- DB telemetry: `uv run iw item-status I-00084 --json`
- Daemon log: `logs/daemon.log` filtered to I-00084
- The S12 (diff-coverage) report from this CR's own run

## Output Files

- `ai-dev/work/I-00084/reports/I-00084_S14_SelfAssess_report.md`
- `ai-dev/work/I-00084/reports/I-00084_S14_SelfAssess_findings.json`

## Focus areas

1. **Did this CR's S12 (diff-coverage) gate run clean on the first try?**
   It should — the fix is now active in this worktree. If it didn't, the
   fix is incomplete and needs another cycle.
2. **What does diff-coverage report on this CR's diff?** Should be ~100%
   on `executor/worktree_setup.sh` (single line, easily covered) and
   the Makefile change (similar). Compare to pre-fix expectation
   (75% × inflated diff).
3. **Cross-CR pattern vs CR-00053's stale-ref problem.** Reference the
   design doc Notes section.
