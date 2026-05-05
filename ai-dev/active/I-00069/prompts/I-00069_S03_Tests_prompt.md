# I-00069_S03_Tests_prompt

**Work Item**: I-00069 -- Downgrade LiveDbConnectionRefusedError to DEBUG/WARNING in test context
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Same policy as S01 — read-only docker introspection only. Testcontainer
fixtures invoked by pytest are an allowed exception (you are unlikely to
need any here).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident does NOT touch migrations. Read-only alembic commands only.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00069 --json`. The `workflow-manifest.json` is a design-time snapshot.
- `ai-dev/active/I-00069/I-00069_Issue_Design.md` — Design document (especially the **Test to Reproduce** and **Regression Prevention** sections)
- `ai-dev/active/I-00069/reports/I-00069_S01_Backend_report.md` — S01 implementation report
- `ai-dev/active/I-00069/reports/I-00069_S02_CodeReview_Backend_report.md` — S02 review report
- `dashboard/app.py` — file under test (post-S01)
- `orch/db/live_db_guard.py` — defines `LiveDbConnectionRefusedError`
- `orch/db/alembic_guard.py` — defines `check_db_at_head()`
- `tests/conftest.py` — for fixture conventions, especially `_arm_live_db_guard`
- `tests/dashboard/test_alembic_guard_banner.py` — existing test in the same area; mirror its setup style

## Output Files

- `tests/dashboard/test_live_db_guard_log_level.py` — NEW test file (the only file you create)
- `ai-dev/active/I-00069/reports/I-00069_S03_Tests_report.md` — Step report

## Context

You are writing the canonical reproduction + regression tests for **I-00069**.

Read the design document. The bug: `dashboard/app.py:146-149` previously
logged the expected `LiveDbConnectionRefusedError` at ERROR with a full
traceback during dashboard test runs. S01 has now narrowed the exception
handling. Your job is to lock that behaviour in.

## Requirements

### 1. Create `tests/dashboard/test_live_db_guard_log_level.py`

The file MUST contain at least these two tests:

#### Test A — Reproduction test (semantic correctness)

```python
def test_i00069_live_db_guard_refusal_is_not_error_in_test_context(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RED before S01, GREEN after.

    Under IW_CORE_TEST_CONTEXT=true, dashboard startup MUST NOT log the
    expected LiveDbConnectionRefusedError at ERROR with a traceback.
    """
```

This test MUST:

- Set `IW_CORE_TEST_CONTEXT=true` via `monkeypatch.setenv(...)`.
- Capture logs at DEBUG-level minimum on the `dashboard.app` logger.
- Call `create_app()` from `dashboard.app` (no surrounding pytest.raises;
  startup must succeed).
- Assert that **no** record with `levelno >= logging.ERROR` mentions
  `LiveDbConnectionRefused` in either `getMessage()` or `exc_text`. Use the
  exact substring `"LiveDbConnectionRefused"` (the error class name).
- Assert that **at least one** DEBUG-level record on the
  `dashboard.app` logger mentions the refusal — i.e., the demoted log
  line is actually emitted. This is the **semantic** assertion — it
  proves the fix took effect, not just that ERROR is absent.
- Assert that `app.state.alembic_guard_status is None` after creation.

#### Test B — Regression test (genuine failures still loud)

```python
def test_i00069_non_refusal_exception_still_logs_error(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Genuine startup failures must STILL log at ERROR with traceback.

    Prevents over-correction where the fix accidentally silences real bugs.
    """
```

This test MUST:

- Use `monkeypatch.setattr` to make `dashboard.app.check_db_at_head`
  (or wherever it is imported into `dashboard.app`) raise
  `RuntimeError("synthetic boot failure")`.
- Call `create_app()`.
- Assert that at least one log record has `levelno == logging.ERROR` and
  that its `exc_text` is non-empty (i.e., `logger.exception` actually
  emitted a traceback).
- Assert that `app.state.alembic_guard_status is None`.

### 2. CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty)
and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES.

For this incident:

- **BAD**: `assert len(caplog.records) > 0` (shape only — passes even if
  the wrong levels are logged).
- **BAD**: `assert any("guard" in r.getMessage() for r in caplog.records)`
  (matches both the buggy ERROR record and the fixed DEBUG record).
- **GOOD**: `assert all(r.levelno < logging.ERROR for r in caplog.records if "LiveDbConnectionRefused" in r.getMessage())` — checks SPECIFIC level for SPECIFIC message.
- **GOOD**: `assert any(r.levelno == logging.DEBUG and "LiveDbConnectionRefused" in r.getMessage() for r in caplog.records)` — proves the demoted line is actually emitted.

### 3. Mind `caplog` defaults

`caplog` is set to WARNING by default in many setups, which would make
Test A trivially pass (no DEBUG records to compare against). Use:

```python
caplog.set_level(logging.DEBUG, logger="dashboard.app")
```

Do NOT set the root logger globally — that would change the behaviour of
unrelated logs in this test session and may flake.

### 4. Avoid live-DB temptations

This test runs under pytest, so `_arm_live_db_guard` from `tests/conftest.py`
will set `IW_CORE_TEST_CONTEXT=true` at session start regardless. Test A's
`monkeypatch.setenv(...)` is therefore largely belt-and-braces, but keep it
explicit for clarity. Do NOT call `importlib.reload(orch.config)` — the
project's testing rules forbid that pattern.

### 5. Falsifiability check

Before declaring done, mentally verify Test A would FAIL on `main`
(pre-S01). The pre-S01 code path emits `logger.exception(...)` at ERROR
with `LiveDbConnectionRefusedError` in `exc_text`. Your assertion must
catch that exact case.

### 6. Type hints and conventions

- Use modern type hints: `pytest.LogCaptureFixture`, `pytest.MonkeyPatch`,
  `-> None`.
- Match the file-header style of `tests/dashboard/test_alembic_guard_banner.py`.
- No `print()` debugging. No `breakpoint()`.
- Use the `# noqa: ...` comments only when an explicit ruff/mypy rule
  requires suppression — never as a blanket silencer.

## Project Conventions

Read:

- `CLAUDE.md` — global rules (NEVER connect tests to live DB; testcontainers only)
- `tests/CLAUDE.md` — fixture conventions, FTS trigger setup, `_arm_live_db_guard`
- `dashboard/CLAUDE.md` — dashboard layout

## TDD Requirement

You are the RED phase. The two tests must:

1. Read S01's implementation and verify your assertions PASS against it.
2. Mentally model what the assertions would do against `main` (pre-S01) and
   confirm Test A would FAIL there. (You cannot check out main; this is an
   analytical check.)

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. **`make format`** — auto-fix and re-stage if needed.
2. **`make typecheck`** — zero errors involving the new test file.
3. **`make lint`** — zero errors.

## Test Verification (NON-NEGOTIABLE)

1. Run `uv run pytest tests/dashboard/test_live_db_guard_log_level.py -q`
   and confirm both tests pass.
2. Run `make test-unit` and confirm zero regressions.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00069",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_live_db_guard_log_level.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "2 passed, 0 failed (file scope); X passed, 0 failed (full unit)",
  "blockers": [],
  "notes": ""
}
```
