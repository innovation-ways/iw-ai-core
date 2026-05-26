# I-00114 S06 CodeReview Report (Review of S04 Tests)

## What was done
- Reviewed design doc sections: Test to Reproduce, AC1..AC5, TDD Approach.
- Reviewed S04 report and changed test files:
  - `tests/unit/test_pi_narration_guard.py`
  - `tests/integration/test_pi_narration_guard.py`
  - `tests/integration/_stub_pi.py`
- Ran required gates:
  - `make lint` ✅
  - `make format-check` ✅
- Re-ran target tests:
  - `uv run pytest tests/unit/test_pi_narration_guard.py tests/integration/test_pi_narration_guard.py -v` ✅ (15 passed)
- Verified no migration files were added/changed.

## Findings
```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00114",
  "reviewed_steps": ["S04"],
  "verdict": "NEEDS_FIX",
  "findings": [
    {
      "severity": "HIGH",
      "category": "isolation",
      "file": "tests/integration/test_pi_narration_guard.py",
      "line": 28,
      "description": "Integration tests seed data under the real project_id ('iw-ai-core'). Per review anchor F, tests must use a unique test-only project_id (e.g. 'test-proj-...') to avoid cross-project pollution risk. Replace hardcoded project_id and helper naming accordingly.",
      "ac_violated": ""
    }
  ],
  "notes": "Assertion strength is otherwise solid (value-specific checks), AC1..AC5 are covered by named tests, subprocess timeout is bounded (10s), and opencode/claude non-guard behavior is asserted."
}
```

## AC coverage map
- AC1: `test_narration_exit_emits_event_and_reprompts`
- AC2: `test_narration_exit_emits_event_and_reprompts`, `test_guard_falls_back_after_5_reprompts`
- AC3: `test_clean_exit_with_step_done_does_not_reprompt`
- AC4: `test_opencode_launch_does_not_use_guard`
- AC5: `test_narration_exit_emits_event_and_reprompts` (reproduction path)

## Files changed by this review step
- `ai-dev/active/I-00114/reports/I-00114_S06_CodeReview_report.md`
