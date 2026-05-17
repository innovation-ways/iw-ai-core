# I-00088 — S04 Code Review (S03 Tests)

## What was reviewed

- Design contract: `ai-dev/active/I-00088/I-00088_Issue_Design.md` (AC2, AC3, TDD Approach, Test to Reproduce)
- S03 implementation report: `ai-dev/active/I-00088/reports/I-00088_S03_Tests_report.md`
- Changed test files:
  - `tests/unit/test_auto_merge_health.py`
  - `tests/integration/test_auto_merge_health_runtime.py`
- Cross-check implementation seam/env behavior:
  - `orch/daemon/auto_merge_health.py`

## Gates run

- `make lint` ✅
- `make format` ✅ (`ruff format --check` reported already formatted)
- `uv run pytest tests/unit/test_auto_merge_health.py tests/integration/test_auto_merge_health_runtime.py -v`
  - Result: **11 passed**
  - Note: command exits non-zero due global coverage threshold (`fail_under=50%`) when running a narrow file subset; there were no test-case failures.

## Review findings

No CRITICAL/HIGH/MEDIUM findings.

### Checklist outcome

- **AC3 argv-shape assertions:** mocked-subprocess unit tests assert argv seam (`bash`, `step_executor_lib.sh`, `auto_merge_resolve`, resolved `cli_tool`, resolved `model`) via `_assert_probe_subprocess_shape(...)`.
- **I003 semantic-strength risk:** tests do not rely only on `runtime_reachable`; mocked subprocess tests include argv assertions.
- **Integration proof shape (AC2):** test uses real executable shim (`opencode`) in `tmp_path`, prepends via `monkeypatch.setenv("PATH", ...)`, and asserts capture content includes both model and probe prompt.
- **Pre-fix regression catchability:** with old `step_executor.sh --step-type ...` path, expected failure before runtime invocation would break these assertions (shim capture/path assertions and reachable expectations), so regression is meaningfully locked.
- **Isolation under pytest-randomly:** uses `tmp_path` and `monkeypatch.setenv`, no raw global env mutation.
- **tests/CLAUDE.md compliance:** no live DB dependency, no `importlib.reload(orch.config)`, integration test correctly under `tests/integration/`.
- **Public seam assertions:** tests assert against `subprocess.run` argv seam, not private module internals.
- **Design-named files present:** both required files are present and modified in S03.

## Output contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00088",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make lint: pass; make format: pass; targeted pytest: 11 passed (coverage gate failure due subset run, no test-case failures)",
  "notes": "No mandatory fixes."
}
```
