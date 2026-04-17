# CR-00008 S10 — Code Review of S09 (Tests)

**Work Item**: CR-00008
**Step**: S10
**Agent**: code-review-impl
**Reviews**: S09

---

## Input Files

- `ai-dev/active/CR-00008/CR-00008_CR_Design.md`
- `ai-dev/active/CR-00008/prompts/CR-00008_S09_Tests_prompt.md`
- `ai-dev/active/CR-00008/reports/CR-00008_S09_Tests_report.md`
- All new or modified files under `tests/dashboard/`

## Output Files

- `ai-dev/active/CR-00008/reports/CR-00008_S10_CodeReview_report.md`

## Review Checklist

### Coverage vs. acceptance criteria

Walk every AC in the design doc and verify at least one test maps to it:

- [ ] AC1 panel mounts — template or browser test
- [ ] AC2 collapse + drawer — browser test
- [ ] AC3 SSE wire format — `test_code_qa_sse_wire.py` (all 7 cases)
- [ ] AC4 markdown streaming without jank/XSS — `test_chat_security.py` + renderer test (if present)
- [ ] AC5 code blocks with copy + highlight — template test + browser test
- [ ] AC6 GFM tables + CSV — template or browser test
- [ ] AC7 citations + sources panel — template test + browser stub
- [ ] AC8 Mermaid ELK — `test_chat_mermaid.py` (S07's suite)
- [ ] AC9 Mermaid failure chip — same
- [ ] AC10 per-message actions — template + browser
- [ ] AC11 scroll behavior — browser
- [ ] AC12 keyboard + slash — browser
- [ ] AC13 image input 501 stub — SSE wire test + browser
- [ ] AC14 accessibility — `test_chat_a11y.py`
- [ ] AC15 license compliance — `test_chat_security.py` (licenses section)

Flag any AC with zero test as **HIGH**.

### Test quality

- [ ] No test hits the live DB on port 5433.
- [ ] No test mocks the DB for an integration-marked test.
- [ ] All SSE tests mock `QAEngine.answer_stream`; no Ollama calls.
- [ ] Browser tests marked with `@pytest.mark.browser`.
- [ ] No hardcoded absolute paths; use fixtures and `tmp_path`.
- [ ] Assertions check observable behavior, not implementation details (no brittle selector trees).

### Conformance to `tests/CLAUDE.md`

- [ ] testcontainers used correctly (if any integration tests touch DB).
- [ ] No `importlib.reload(orch.config)`.
- [ ] FTS SQL functions applied in DB-integration fixtures (if any).

### Hygiene

- [ ] `ruff check tests/` clean.
- [ ] Each test file < 400 lines.
- [ ] Descriptive test names.

## Severity definitions

Same as prior CodeReview steps. Missing coverage for a CRITICAL-path AC (AC3, AC4, AC8, AC9, AC14, AC15) is **CRITICAL**.

## Subagent Result Contract

```json
{
  "step": "S10",
  "agent": "code-review-impl",
  "work_item": "CR-00008",
  "completion_status": "complete",
  "reviewed_step": "S09",
  "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "blocking_next_step": false,
  "notes": ""
}
```
