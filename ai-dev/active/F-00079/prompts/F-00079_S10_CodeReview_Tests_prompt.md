# F-00079_S10_CodeReview_Tests_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Step Being Reviewed**: S09 (tests-impl)
**Review Step**: S10

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers in pytest fixtures are EXEMPT.

## ⛔ Migrations: agents generate, daemon applies

Run migrations only inside testcontainer fixtures.

## Input Files

- `ai-dev/active/F-00079/F-00079_Feature_Design.md`
- `ai-dev/active/F-00079/reports/F-00079_S09_Tests_report.md`
- All test files added in S09
- `tests/CLAUDE.md` — testing rules

## Output Files

- `ai-dev/active/F-00079/reports/F-00079_S10_CodeReview_Tests_report.md`

## Context

You are reviewing the test suite for **F-00079**. Coverage must satisfy every Acceptance Criterion (AC1..AC8), every Boundary Behavior row, every Invariant, and follow the project test rules in `tests/CLAUDE.md`.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in S09's changed files → CRITICAL findings.

## Review Checklist

### 1. AC Coverage Map

For each AC1..AC8, identify the specific test(s) that cover it. Any AC without a corresponding test → CRITICAL with `category: "testing"`.

| AC | Test(s) found | Notes |
|---|---|---|
| AC1 (live diff for in-progress) | | |
| AC2 (step toggle drilldown) | | |
| AC3 (archived item still has diff) | | |
| AC4 (PDF export) | | |
| AC5 (untracked artifacts preserved) | | |
| AC6 (generated files auto-collapse) | | |
| AC7 (per-step diff captured at step-done) | | |
| AC8 (aggregate diff captured at squash merge) | | |

Fill this table in your review report.

### 2. Boundary Behavior Coverage

Every row in the design's Boundary Behavior table → at least one assertion or parametrize case. Missing rows → MEDIUM (fixable) or HIGH depending on severity.

### 3. Invariant Coverage

| Invariant | Test |
|---|---|
| 1: Files tab reachable for all states | |
| 2: /tab/artifacts → 404 | |
| 3: /artifact-raw still works | |
| 4: step-done unaffected by capture failure | |
| 5: merge unaffected by capture failure | |
| 6: append-only safety | |
| 7: resolver returns None instead of raising | |
| 8: single-source-of-truth glob list | |
| 9: item_artifacts.html removed | |
| 10: archived items load diff from DB | |

### 4. Test Hygiene (`tests/CLAUDE.md`)

- No live-DB connections. Search for `5433`, `IW_CORE_DB_HOST`, `localhost:5433` in test files; flag any usage outside testcontainer fixtures.
- testcontainer URL replacement: `postgresql+psycopg2://` → `postgresql+psycopg://` performed.
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` run after `Base.metadata.create_all()`.
- No `importlib.reload(orch.config)`; `monkeypatch.delenv()` used instead.
- No DB mocking in integration tests.
- `DaemonEvent.metadata` access uses `event_metadata`.

### 5. Test Isolation

- Each test creates its own state and cleans up.
- No order dependencies (tests can run in any order, in parallel).
- Fixtures scoped appropriately (function vs session).
- No global state mutated.

### 6. Browser Test Quality

- Uses `playwright-cli` exclusively (no `chromium.launch`, no `agent-browser`).
- `playwright-cli kill-all` at start.
- Assertions are concrete (specific text, specific element refs after `snapshot`).
- Screenshots captured at meaningful states (kept under `evidences/post/` for QV browser, but unit browser tests can also document state).

### 7. Test Naming and Organisation

- Unit tests under `tests/unit/`.
- Integration tests under `tests/integration/`.
- Browser tests under `tests/dashboard/browser/`.
- Names follow `test_<module>_<scenario>` for unit; `test_<feature>_<flow>` for integration.

### 8. Performance / Reliability

- No flaky tests (no `time.sleep` outside justified cases; use `wait_for` patterns).
- No external network calls (everything mocked or local fixtures).

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
make test-frontend
```

All must pass with zero failures.

## Severity Levels

| Severity | Meaning | Action |
|---|---|---|
| CRITICAL | Missing AC coverage, live-DB connection, mock DB in integration | Must fix |
| HIGH | Missing Boundary or Invariant coverage, flaky test | Must fix |
| MEDIUM (fixable) | Naming, organisation, minor coverage gap | Should fix |
| MEDIUM (suggestion) | Better assertion pattern available | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "CodeReview",
  "work_item": "F-00079",
  "step_reviewed": "S09",
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit, Y integration, Z frontend, 0 failed",
  "ac_coverage": {
    "AC1": "test_name", "AC2": "...", "...": ""
  },
  "notes": ""
}
```
