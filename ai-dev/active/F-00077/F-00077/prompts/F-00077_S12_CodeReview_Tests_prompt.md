# F-00077_S12_CodeReview_Tests_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step Being Reviewed**: S11 (tests-impl)
**Review Step**: S12

---

## ⛔ Docker / Migrations off-limits

Same constraints. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md`
- `ai-dev/active/F-00077/reports/F-00077_S11_Tests_report.md`
- All test files in S11's `files_changed`

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S12_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in S11's files → CRITICAL.

## Review Checklist

### 1. Coverage Mapping

- Cross-reference the design's Boundary Behavior table — every row should have a corresponding test in S01-S08 OR S11. Identify any row not covered. Each missing row is a CRITICAL finding.
- Cross-reference the design's Invariants — each should map to a test (per the design template). Missing invariant test → HIGH.
- Cross-reference all 9 ACs — each must have at least one test asserting the success path. Missing AC test → CRITICAL.

### 2. Test Isolation

- No test depends on another test's database state.
- No test uses the live DB on port 5433. All use `db_session` testcontainer fixture.
- LLM stubs are scoped properly (no leak across tests via global state).
- Each test cleans up its conversations / messages — or relies on testcontainer-rollback (acceptable per project convention).

### 3. Test Quality

- Test names clearly describe what is verified (e.g. `test_summary_preserves_identity_facts` not `test_summary_works`).
- Each test has at least one explicit assertion (no smoke tests that just call code without checking).
- Negative paths exercise the actual error class (e.g. `pytest.raises(ConnectionError)`, NOT `pytest.raises(Exception)`).
- Multi-turn integration test asserts BOTH user message AND assistant message persistence, not just one side.

### 4. Project Conventions

- File paths under `tests/unit/`, `tests/integration/`, `tests/dashboard/` per the project layout.
- Test files named `test_*.py`.
- Fixtures imported from `tests/conftest.py` not redefined locally.

### 5. Determinism

- No `time.sleep(...)` for "wait for daemon" — use direct function calls or testcontainer-friendly polling.
- No reliance on real Ollama / LanceDB. Both are stubbed at the module level.
- No reliance on system clock for TTL tests — `monkeypatch.setattr(time, "time", ...)` or equivalent.

### 6. Safety

- No tests connect to live DB even by accident (grep for `5433`, `IW_CORE_DB_PORT`).
- No tests touch real worktrees or Docker.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

ALL tests pass. ZERO regressions in pre-existing test suite.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Missing AC test, missing Boundary Behavior test row, test connects to live DB, test relies on real Ollama | Must fix |
| HIGH | Missing Invariant test, broad-exception assertion, fragile time-based test | Must fix |
| MEDIUM (fixable) | Test name unclear, missing assertion message, fixture duplication | Fix in fix cycle |

## Review Result Contract

```json
{
  "step": "S12",
  "agent": "code-review-impl",
  "work_item": "F-00077",
  "step_reviewed": "S11",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
