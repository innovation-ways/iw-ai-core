# CR-00058_S06_CodeReview_FIX_prompt

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S06 (code-review-fix-impl)
**Addresses Findings From**: S05 (code-review-impl)

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Input Files

- `ai-dev/active/CR-00058/reports/CR-00058_S05_CodeReview_findings.json` — the findings to address
- `ai-dev/active/CR-00058/CR-00058_CR_Design.md`
- All files under `scope.allowed_paths`
- Runtime step state via `uv run iw item-status CR-00058 --json`

## Output Files

- `ai-dev/active/CR-00058/reports/CR-00058_S06_CodeReview_FIX_report.md`
- Modifications to files in `scope.allowed_paths` necessary to resolve CRITICAL and HIGH findings

## Requirements

1. **Address every CRITICAL and HIGH finding.** Skip LOW unless trivial; record skipped findings in the report with rationale.
2. **MEDIUM**: address if the fix is local and low-risk; defer with rationale otherwise.
3. **Re-run targeted tests** for any code you touched (S01's unit tests for `scope_overlap.py` / `project_registry.py`; S02's integration test if you change `batch_manager.py`).
4. **Stay in scope.** Do not introduce changes outside `scope.allowed_paths`.
5. **Update reports** rather than discarding prior context.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Targeted re-runs only. Do NOT run `make test-unit` / `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-fix-impl",
  "work_item": "CR-00058",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "...", "typecheck": "...", "lint": "..."},
  "tests_passed": true,
  "test_summary": "...",
  "tdd_red_evidence": "n/a — fix step; behavioural tests written in S01/S02",
  "findings_addressed": ["F1", "F3", "..."],
  "findings_deferred": [{"id": "F7", "reason": "..."}],
  "blockers": [],
  "notes": ""
}
```
