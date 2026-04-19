# F-00055_S06_CodeReview_prompt

**Work Item**: F-00055 — Work-item-aware code chat
**Step**: S06
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` (AC2, AC6, AC7, AC9, AC10; Invariants 3, 4, 6)
- `ai-dev/active/F-00055/reports/F-00055_S05_API_report.md`
- `dashboard/routers/code_qa.py` + new test files from S05

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S06_CodeReview_report.md`

## Review Focus

Review S05 (SSE protocol extension). Findings with CRITICAL/HIGH/MEDIUM/LOW.

### Must-check items

1. **Event shape compliance (Invariant 4)** — every `citation` event for a work-item source carries both `work_item_type` and `work_item_id`; format regex enforced.
2. **Backward compatibility (Invariant 3)** — code-only pipeline emits zero `phase` events; existing clients do not break.
3. **Thread-bridge queue** — queue now carries dicts, not strings; None-sentinel still terminates; error path still works.
4. **Symbol-hint flow (AC7)** — `findusages` chip correctly extracts symbol from the user question and passes it to the engine.
5. **Router thinness** — no business logic leaked into the router (per `dashboard/CLAUDE.md`).
6. **Error handling** — engine exceptions emit `event: error` and don't corrupt the SSE stream.
7. **Test coverage** — three test files exist and exercise phase events, citation payload shapes, findusages routing.
8. **No regressions to `/api/projects/{id}/code/qa-with-image`** — the 501 stub is untouched.

## Review Output Format

Same as S02: findings table + verdict + result contract.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00055",
  "completion_status": "complete",
  "review_verdict": "approve|approve-with-fixes|reject",
  "findings_critical": 0,
  "findings_high": 0,
  "findings_medium": 0,
  "findings_low": 0,
  "notes": ""
}
```
