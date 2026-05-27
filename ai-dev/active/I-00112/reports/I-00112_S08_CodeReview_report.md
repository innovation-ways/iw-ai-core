# I-00112 S08 — CodeReview (S07 Tests)

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "I-00112",
  "step_reviewed": "S07",
  "verdict": "fail",
  "findings": [
    {
      "severity": "HIGH",
      "file": "tests/unit/test_keep_alive_poller_success_contract.py",
      "test": "test_i00112_poller_logs_failed_when_contract_violated",
      "issue": "Reproduction test does not validate persisted DB row. It mocks _log_run and asserts kwargs, but the contract requires asserting row.status in ('failed','retried_failed') plus row.returncode==0 and row.elapsed_ms<500 from stored KeepAliveRun data."
    },
    {
      "severity": "HIGH",
      "file": "tests/unit/test_keep_alive_poller_success_contract.py",
      "tests": [
        "test_i00112_poller_persists_captured_fields",
        "test_i00112_poller_logs_failed_when_contract_violated"
      ],
      "issue": "Design required DB-backed tests (slot row + persisted KeepAliveRun verification). Current tests mock SessionLocal/log path, so they do not prove persistence behavior end-to-end."
    },
    {
      "severity": "MEDIUM (fixable)",
      "file": "tests/dashboard/test_keep_alive_runs_table.py",
      "test": "test_recent_runs_table_renders_em_dash_for_null_diagnostic_fields",
      "issue": "Assertion strength is weak: only checks '—' appears somewhere in HTML, not that both Elapsed and Output cells render fallback explicitly."
    }
  ],
  "mandatory_fix_count": 2,
  "tests_passed": true,
  "test_summary": "24 passed, 0 failed",
  "notes": "make lint and make format-check passed. Required targeted pytest command passed. Six named reproduction tests are present in tests/unit/test_keep_alive_poller_success_contract.py; dashboard tests exist under tests/dashboard/."
}
```

## Commands run
- `make lint` ✅
- `make format-check` ✅
- `uv run pytest tests/unit/test_keep_alive_poller_success_contract.py tests/unit/test_keep_alive_service.py tests/unit/test_keep_alive_poller.py tests/dashboard/test_keep_alive_runs_table.py -v` ✅ (24 passed)

## Files reviewed
- `ai-dev/active/I-00112/I-00112_Issue_Design.md`
- `ai-dev/active/I-00112/reports/I-00112_S07_Tests_report.md`
- `skills/iw-ai-core-testing/SKILL.md`
- `tests/unit/test_keep_alive_poller_success_contract.py`
- `tests/unit/test_keep_alive_service.py`
- `tests/unit/test_keep_alive_poller.py`
- `tests/dashboard/test_keep_alive_runs_table.py`
