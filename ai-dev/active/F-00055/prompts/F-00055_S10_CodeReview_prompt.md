# F-00055_S10_CodeReview_prompt

**Work Item**: F-00055 — Work-item-aware code chat
**Step**: S10
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` — ALL Acceptance Criteria, Boundary Behavior, Invariants
- `ai-dev/active/F-00055/reports/F-00055_S09_Tests_report.md`
- All test files created in S09 and the eval-set fixture

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S10_CodeReview_report.md`

## Review Focus

Review S09 (tests + eval set). Findings with CRITICAL/HIGH/MEDIUM/LOW.

### Must-check items

1. **AC coverage completeness** — every AC in the design doc has at least one test asserting its Then clause.
2. **Boundary-behavior coverage** — every row of the Boundary Behavior table has a corresponding test.
3. **Invariant coverage** — each invariant has at least one test that would fail if the invariant were violated.
4. **Eval set realism** — tuples reference actual work items from the current iw-ai-core project (not fabricated IDs); at least 10 tuples; negative controls present.
5. **No live-DB connections** — tests use testcontainers only; no port 5433.
6. **FTS trigger setup** — tests that seed `WorkItem` rows run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `create_all()` (per `tests/CLAUDE.md`).
7. **Classifier mocking** — classifier LLM call is mocked deterministically in CI; no flakiness from live Ollama.
8. **Project isolation** — at least one test explicitly verifies Invariant 9 (no cross-project leakage).
9. **No regression test** — the "code-only-question still works" test is present and passes.
10. **Fixture quality** — `eval_set_f00055.json` is valid JSON, well-documented, and diverse (functional + technical + slash-override + negative control).

## Review Output Format

Same as S02: findings table + verdict + result contract.

## Subagent Result Contract

```json
{
  "step": "S10",
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
