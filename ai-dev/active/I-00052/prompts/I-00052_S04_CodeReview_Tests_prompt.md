# I-00052_S04_CodeReview_Tests_prompt

**Work Item**: I-00052 — E2E dashboard container crash logs not captured — fix-cycle agents blind to startup failures
**Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these two commands on the files listed in the
implementation report's `files_changed`. Fix nothing yourself — only report.

```bash
make lint          # ruff check — catches ARG001, F811, unused imports, etc.
make format        # ruff format --check — catches formatting drift
```

If either command reports NEW violations, classify each as **CRITICAL** with
`"category": "conventions"`, `"file"`, `"line"`, and `"description"`.

## Input Files

- `ai-dev/active/I-00052/I-00052_Issue_Design.md` — acceptance criteria
- `ai-dev/active/I-00052/reports/I-00052_S03_Tests_report.md` — S03 report
- `tests/unit/test_browser_env.py` — new tests

## Output Files

- `ai-dev/active/I-00052/reports/I-00052_S04_CodeReview_Tests_report.md` — review report

## Review Checklist

### Reproduction Test Existence
- [ ] A test exists that would fail before the fix (`_capture_crashed_container_logs` did not exist → `ImportError`) and passes after

### Semantic Correctness (CRITICAL — I003 Lesson)
- [ ] Happy path test verifies `mock_run` called with EXACT args including container name and `"--tail", "50"` — not just `assert mock_run.called`
- [ ] Happy path test verifies SPECIFIC crash log content in result (e.g., `"ImportError"`)
- [ ] No-op test asserts result is EXACTLY `""` (not just falsy)
- [ ] No-op test asserts `mock_run.assert_not_called()` — proves no subprocess was spawned

### Coverage
- [ ] Docker unavailable (FileNotFoundError) → no raise, fallback note in result
- [ ] Docker timeout (TimeoutExpired) → no raise, fallback note in result
- [ ] No "exited" lines in compose log → empty result, no subprocess
- [ ] Same container name appears twice → subprocess called exactly once (deduplication)

### Test Isolation
- [ ] All tests mock `subprocess.run` — no live Docker daemon required
- [ ] No testcontainer dependency (these are unit tests)
- [ ] Tests import only from `orch.daemon.browser_env` — no DB imports

### Format / Lint
- [ ] `make lint` passes on test file (no ARG001, no unused imports)
- [ ] `make format-check` passes on test file

## Severity Rubric

| Severity | Meaning |
|----------|---------|
| CRITICAL | Shape-checking only (no specific content verified), or mock not verifying exact args |
| HIGH | Missing deduplication test or missing timeout/exception test |
| MED | No-op case missing `assert_not_called()` |
| LOW | Minor naming or style |

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00052",
  "overall_status": "pass|fail",
  "mandatory_fix_count": 0,
  "findings": []
}
```

Then call:
```bash
uv run iw step-done I-00052 --step S04 \
  --report ai-dev/active/I-00052/reports/I-00052_S04_CodeReview_Tests_report.md
```
