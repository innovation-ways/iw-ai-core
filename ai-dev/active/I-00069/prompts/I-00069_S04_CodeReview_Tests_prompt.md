# I-00069_S04_CodeReview_Tests_prompt

**Work Item**: I-00069 -- Downgrade LiveDbConnectionRefusedError to DEBUG/WARNING in test context
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Read-only docker introspection only. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This incident does NOT touch migrations. Read-only alembic commands only.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00069 --json`. The `workflow-manifest.json` is a design-time snapshot.
- `ai-dev/active/I-00069/I-00069_Issue_Design.md` — Design document
- `ai-dev/active/I-00069/reports/I-00069_S03_Tests_report.md` — S03 implementation report
- `tests/dashboard/test_live_db_guard_log_level.py` — file under review
- `dashboard/app.py` — referenced (post-S01 state, for confirming the tests target the right behaviour)

## Output Files

- `ai-dev/active/I-00069/reports/I-00069_S04_CodeReview_Tests_report.md` -- Review report

## Context

You are reviewing the test file added in S03 for **I-00069**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violation in `tests/dashboard/test_live_db_guard_log_level.py` is a
**CRITICAL** finding (`category: "conventions"`).

## Review Checklist

### 1. Falsifiability (most important)

Walk through each test mentally as if `dashboard/app.py` were still on the
pre-S01 code (`except Exception: logger.exception(...)`). Test A MUST fail
on that code:

- The pre-fix code emits a record with `levelno == logging.ERROR` whose
  `exc_text` contains `"LiveDbConnectionRefusedError"` (the class name).
- Test A's assertion `all(r.levelno < logging.ERROR for r in records if "LiveDbConnectionRefused" in ...)` MUST evaluate False on that record.
- If the assertion would also pass on pre-fix code, the test is a no-op
  and is a CRITICAL finding (`category: "testing"`).

### 2. Semantic correctness, not shape

Reject (CRITICAL `category: "testing"`) any of:

- `assert len(caplog.records) > 0` (shape only)
- `assert "guard" in caplog.text` without a level check (matches both buggy and fixed lines)
- `assert any(...)` checks that don't pin SPECIFIC levels for SPECIFIC messages

Confirm (positive findings, no severity needed):

- Test A asserts a SPECIFIC absent level (`>= logging.ERROR`) for a
  SPECIFIC message substring (`"LiveDbConnectionRefused"`).
- Test A asserts a SPECIFIC present level (`logging.DEBUG`) for the
  demoted line.
- Test A asserts `app.state.alembic_guard_status is None`.
- Test B asserts a non-refused exception STILL fires
  `logger.exception(...)` (level == ERROR + non-empty `exc_text`).

### 3. Logger scope

`caplog.set_level(logging.DEBUG, logger="dashboard.app")` — confirm the
logger name matches the actual logger used in `dashboard/app.py` (it
should be `dashboard.app` because `logger = logging.getLogger(__name__)`
at module level). If the logger name in the test does not match the
actual `__name__`, the DEBUG capture is broken and Test A would falsely
pass with no DEBUG records to compare against — CRITICAL.

### 4. Isolation and side effects

- `monkeypatch.setenv` / `monkeypatch.setattr` is used (auto-reverts on
  teardown). Direct `os.environ[...] = ...` is a CRITICAL `testing` finding.
- No global logger reconfiguration leaking to other tests.
- No live-DB connection attempts (the `_arm_live_db_guard` session
  fixture should make any leakage immediately raise).

### 5. Project conventions

- Read `tests/CLAUDE.md` (test layout, fixture rules).
- File location is `tests/dashboard/` (not `tests/unit/` or `tests/integration/`) because it exercises FastAPI factory + dashboard wiring.
- Modern type hints (`pytest.LogCaptureFixture`, `-> None`, etc.).

### 6. Forbidden patterns (project hard rules)

- `importlib.reload(orch.config)` — forbidden (CLAUDE.md). Reject CRITICAL
  if present.
- Mocking the database in integration tests — N/A here (this is a
  dashboard test, no DB needed).
- Connecting to live DB on port 5433 — the guard prevents it; if the
  test attempts it, the guard will refuse and the test will error in a
  way that masks the actual assertion. Reject CRITICAL.

## Test Verification (NON-NEGOTIABLE)

1. Run `uv run pytest tests/dashboard/test_live_db_guard_log_level.py -q`
   and confirm both tests pass against the post-S01 code.
2. Run `make test-unit` and confirm zero regressions.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Test is a no-op, shape-only, or violates project hard rules | Must fix |
| **HIGH** | Significant gap in coverage / correctness | Must fix |
| **MEDIUM (fixable)** | Convention violation, fragile assertion | Should fix |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00069",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "tests/dashboard/test_live_db_guard_log_level.py",
      "line": 0,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2 passed, 0 failed (file scope); X passed, 0 failed (full unit)",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH and zero MEDIUM_FIXABLE; otherwise `fail`.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
