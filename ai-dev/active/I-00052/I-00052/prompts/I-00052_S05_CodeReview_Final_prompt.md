# I-00052_S05_CodeReview_Final_prompt

**Work Item**: I-00052 — E2E dashboard container crash logs not captured — fix-cycle agents blind to startup failures
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md
Exception: `docker logs` (read-only) is used by the new helper — this is permitted.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run:

```bash
make lint
make format
```

Any new violations in changed files → CRITICAL finding with `"category": "conventions"`.

## Input Files

- `ai-dev/active/I-00052/I-00052_Issue_Design.md` — full description and acceptance criteria
- `ai-dev/active/I-00052/reports/I-00052_S01_Backend_report.md`
- `ai-dev/active/I-00052/reports/I-00052_S02_CodeReview_Backend_report.md`
- `ai-dev/active/I-00052/reports/I-00052_S03_Tests_report.md`
- `ai-dev/active/I-00052/reports/I-00052_S04_CodeReview_Tests_report.md`
- `orch/daemon/browser_env.py`
- `orch/daemon/batch_manager.py`
- `tests/unit/test_browser_env.py`

## Output Files

- `ai-dev/active/I-00052/reports/I-00052_S05_CodeReview_Final_report.md` — final review report

## Context

Global cross-layer review of I-00052. The fix adds `_capture_crashed_container_logs` to `browser_env.py` and calls it from `batch_manager.py` to append container application stderr to `StepRun.error_message` when the E2E dashboard container crashes.

## Review Checklist

### Bug Fix Completeness
- [ ] AC1: `StepRun.error_message` will include "Container Crash Logs" when a container exits (1)
- [ ] AC2: No exception possible from the helper — all subprocess calls inside `except Exception`
- [ ] AC3: Empty compose log → empty string, no subprocess call
- [ ] `batch_manager.py` passes the FULL compose output to the helper (not just `log_tail`)

### Implementation Safety
- [ ] `subprocess.run` uses list form (not `shell=True`)
- [ ] Both stdout AND stderr captured from `docker logs`
- [ ] `timeout=10` present — prevents blocking the failure-recording path
- [ ] `# noqa: S603` and `# noqa: BLE001` present where needed
- [ ] No new imports beyond what `browser_env.py` already had

### Test Semantic Correctness (CRITICAL)
- [ ] Happy path test verifies specific docker args AND specific crash log content
- [ ] No-op tests assert exactly `""` and `assert_not_called()`
- [ ] Exception/timeout tests verify no raise AND fallback note in result
- [ ] Deduplication test verifies `mock_run` called exactly once

### Cross-Layer Integration
- [ ] `batch_manager.py` import of `browser_env` already exists (not newly added)
- [ ] The `error_msg` format — compose tail first, then crash logs — is correct for fix-cycle prompt readability
- [ ] No other functions modified in either file

## Severity Rubric

| Severity | Meaning |
|----------|---------|
| CRITICAL | Helper can raise; `shell=True`; full compose output not passed; `except` too narrow |
| HIGH | stdout-only capture; missing deduplication; missing timeout |
| MED | noqa comments missing; minor format issue |
| LOW | Style nit |

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00052",
  "overall_status": "pass|fail",
  "mandatory_fix_count": 0,
  "findings": []
}
```

Then call:
```bash
uv run iw step-done I-00052 --step S05 \
  --report ai-dev/active/I-00052/reports/I-00052_S05_CodeReview_Final_report.md
```
