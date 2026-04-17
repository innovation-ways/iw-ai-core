# CR-00008 S12 — Fix Findings from S11 (Cross-Agent Final Review)

**Work Item**: CR-00008
**Step**: S12
**Agent**: code-review-fix-final-impl

---

## Input Files

- `ai-dev/active/CR-00008/CR-00008_CR_Design.md`
- `ai-dev/active/CR-00008/reports/CR-00008_S11_CodeReviewFinal_report.md` — the source of findings to fix
- All files in the changeset so far

## Output Files

- Modified source files as needed to resolve **every CRITICAL and HIGH** finding from S11
- `ai-dev/active/CR-00008/reports/CR-00008_S12_CodeReviewFixFinal_report.md`

## Scope

Resolve **every CRITICAL and HIGH** finding in the S11 report. MEDIUM and LOW findings are addressed if the fix is trivial; otherwise leave them with a comment citing the S11 finding id and tracked in the report's "Deferred" section.

## Rules

- Do not re-open scope. If a finding proposes an out-of-scope refactor, fix only the minimum required to pass the gate and note the scope issue in the report.
- Re-run the full suite after each fix batch:
  ```bash
  uv run ruff check .
  uv run mypy orch/ dashboard/
  uv run pytest tests/dashboard/ -v
  ```
- Zero regressions tolerated. If a fix causes a previously-passing test to fail, revert and take a narrower approach.
- No new dependencies introduced at this stage unless a CRITICAL security finding requires it (document in report).

## Report structure

```markdown
## S11 Findings Triage
| ID | Severity | Action | Evidence |
|----|----------|--------|----------|
| F1 | CRITICAL | Fixed in `path:line` | test_X added/updated |
| F2 | HIGH | Fixed in `path:line` | — |
| F3 | MEDIUM | Deferred — out of scope | tracking: ... |

## Fix Summary
- <one-line description of each change>

## Regression Check
- ruff: PASS
- mypy: PASS
- pytest unit: X passed
- pytest integration: Y passed
```

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00008",
  "completion_status": "complete|partial|blocked",
  "findings_fixed": {"critical": 0, "high": 0, "medium": 0},
  "findings_deferred": [],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
