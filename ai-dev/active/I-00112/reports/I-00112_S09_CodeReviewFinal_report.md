# I-00112 S09 — Final Cross-Agent Code Review

## Verdict
**FAIL**

## What I reviewed
- Item/status and design docs:
  - `ai-dev/active/I-00112/I-00112_Issue_Design.md`
  - `ai-dev/active/I-00112/I-00112_Functional.md`
  - `uv run iw item-status I-00112 --json`
- Reports S01..S08
- Implemented files across S01/S03/S05/S07 (including additional files reported)

## Required gates run
- `make lint` ✅ PASS
- `make format-check` ✅ PASS
- `make test-unit` ✅ PASS (`3605 passed, 7 skipped, 0 failed`)
- `make migration-check` ✅ PASS (`3 passed, 0 failed`)

## Cross-cutting review result

### 1) Schema ↔ ORM ↔ runtime persistence
- Migration adds: `stdout`, `stderr`, `elapsed_ms`, `returncode` (all nullable) ✅
- `KeepAliveRun` model defines matching mapped attributes/types ✅
- Poller `_log_run` writes all four fields on every call ✅

### 2) Backend ↔ Frontend
- Template uses `run.elapsed_ms`, `run.stdout`; both exist on `KeepAliveRun` ✅
- Router `/api/keep-alive/runs` passes ORM `runs` directly ✅

### 3) Success contract single source
- Contract is centralized in `FireResult.is_success` ✅
- Poller consults `result.is_success` (no inline re-derivation) ✅
- Single numeric constant source is `MIN_SUCCESS_ELAPSED_MS = 500`; no magic `500` duplication in service/poller logic ✅

### 4) Test boundary
- New success-contract tests mock `subprocess.run` (not `fire_claude`) ✅

### 5) AC mapping
- AC1: `test_i00112_poller_logs_failed_when_contract_violated` + `_fire_slot` uses `is_success` ✅
- AC2: `test_i00112_real_round_trip_is_success` + `_fire_slot` uses `is_success` ✅
- AC3: six tests in `tests/unit/test_keep_alive_poller_success_contract.py` present and passing ✅
- AC4: fragment updated + `tests/dashboard/test_keep_alive_runs_table.py` ✅
- AC5: `make migration-check` passing in S01/S09 ✅

### 6) Functional ↔ technical consistency
- Functional doc prediction (stricter success, Elapsed/Output, legacy `—`) matches implemented UI behavior ✅

### 7) Security
- `title` attribute uses escaped stdout: `{{ run.stdout|e }}` ✅

## Findings

1. **CRITICAL** — Scope cleanliness violation (`cross_cutting: true`)
   - `tests/integration/test_keep_alive_poller_success_contract.py` was added and `tests/integration/test_keep_alive_poller_integration.py` was modified, but integration-test paths are outside the design doc’s declared **Impacted Paths** for this item.
   - Per S09 scope rule, any shipped file outside declared impacted paths is CRITICAL.

## Review contract JSON
```json
{
  "step": "S09",
  "agent": "CodeReview_Final",
  "work_item": "I-00112",
  "steps_reviewed": ["S01", "S03", "S05", "S07"],
  "verdict": "fail",
  "findings": [
    {
      "severity": "CRITICAL",
      "title": "Scope cleanliness violation: integration test files outside declared impacted paths",
      "files": [
        "tests/integration/test_keep_alive_poller_success_contract.py",
        "tests/integration/test_keep_alive_poller_integration.py"
      ],
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "3605 unit passed, migration-check PASS, 0 failed",
  "missing_requirements": [],
  "notes": "AC1..AC5 demonstrations cross-referenced above."
}
```
