# CR-00058_S08_CodeReview_FIX_Final_prompt

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S08 (code-review-fix-final-impl)
**Addresses Findings From**: S07 (code-review-final-impl)

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Input Files

- `ai-dev/active/CR-00058/reports/CR-00058_S07_CodeReview_Final_findings.json`
- `ai-dev/active/CR-00058/CR-00058_CR_Design.md`
- All files under `scope.allowed_paths`
- Runtime step state via `uv run iw item-status CR-00058 --json`

## Output Files

- `ai-dev/active/CR-00058/reports/CR-00058_S08_CodeReview_FIX_Final_report.md`
- Modifications to files in `scope.allowed_paths`

## Requirements

1. **Address every CRITICAL and HIGH finding** from S07.
2. **MEDIUM**: address if low-risk; defer with rationale otherwise.
3. **Re-run targeted tests** for any code touched. Full suites are S12/S13's job.
4. **Stay in scope.**
5. **Verify cross-layer changes** end-to-end if your fix touches the layer boundary (e.g., a router contract change must also be reflected in templates).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Targeted only.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00058",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "...", "typecheck": "...", "lint": "..."},
  "tests_passed": true,
  "test_summary": "...",
  "tdd_red_evidence": "n/a — final fix step; behavioural tests live in S01/S02",
  "findings_addressed": [],
  "findings_deferred": [],
  "blockers": [],
  "notes": ""
}
```
