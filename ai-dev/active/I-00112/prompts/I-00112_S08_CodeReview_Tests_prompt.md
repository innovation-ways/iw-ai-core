# I-00112_S08_CodeReview_Tests_prompt

**Work Item**: I-00112 -- Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires
**Step Being Reviewed**: S07 (Tests)
**Review Step**: S08

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. S07 did not touch migrations.

## Input Files

- `uv run iw item-status I-00112 --json`.
- `ai-dev/active/I-00112/I-00112_Issue_Design.md` — design (especially **Test to Reproduce**, **AC3**, **Regression Prevention**).
- `ai-dev/active/I-00112/reports/I-00112_S07_Tests_report.md` — S07 step report.
- All files listed in S07's `files_changed`.
- `skills/iw-ai-core-testing/SKILL.md` — assertion strength rules.

## Output Files

- `ai-dev/active/I-00112/reports/I-00112_S08_CodeReview_report.md`.

## Context

You are reviewing S07 (Tests). The step authored a new file `tests/unit/test_keep_alive_poller_success_contract.py` with the six reproduction + regression tests named in the design, updated `test_keep_alive_service.py` and `test_keep_alive_poller.py` to match S03's `FireResult` signature, and added a `tests/dashboard/test_keep_alive_runs_table.py` covering the NULL fallback and populated rendering of the new columns.

## Read the Design Document FIRST

- **Test to Reproduce** — list every test name. EVERY name must appear in S07's `files_changed` and ALL must be present in the new file. Missing tests are CRITICAL.
- **AC3** — `pytest -v` must report all six passing.
- **Regression Prevention** — the design says the test boundary was deliberately moved from `fire_claude` (wrapper) to `subprocess.run` (the real decision point). Tests that mock at the wrong boundary are HIGH.
- **AC4** — the dashboard render tests are part of the contract.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations in S07's `files_changed` are CRITICAL.

## Review Checklist

### 1. Test presence

- All six test names from **Test to Reproduce** appear in `tests/unit/test_keep_alive_poller_success_contract.py` (or in the integration file if S07 moved 5/6 there). Missing test → **CRITICAL**.
- The dashboard render tests (NULL fallback + populated values) exist under `tests/dashboard/`. Missing → CRITICAL.

### 2. Boundary correctness

- The success-contract tests mock at `orch.keep_alive_service.subprocess.run` (or equivalent path), NOT at `fire_claude`. Mocking at `fire_claude` re-introduces the bug class's blind spot — HIGH.
- `time.perf_counter` is also mocked (else elapsed_ms is wall-time and tests are flaky). Tests that rely on real elapsed without mocking are HIGH.

### 3. Assertion strength (I003 lesson)

Per `skills/iw-ai-core-testing/SKILL.md` and the prompt's verbatim warning — flag any:

- `assert <key> in <dict>` without checking the value → MEDIUM (fixable).
- `assert len(<x>) > 0` → MEDIUM (fixable).
- `assert <x> != <y>` where the expected set is known → MEDIUM (fixable) (should be `in (<known_values>)`).
- `assert "Elapsed" in html` without `>Elapsed<` anchoring → MEDIUM (suggestion) (likely fine here because the only place "Elapsed" can appear is the header, but anchoring is stronger).

### 4. Reproduction test value

For `test_i00112_poller_logs_failed_when_contract_violated` specifically:
- It must mock `subprocess.run` such that BOTH attempts (first + retry) yield rc=0 / empty stdout / fast elapsed.
- It must assert `row.status in ("failed", "retried_failed")` — NOT `assert row.status != "success"` (the negative-only form is HIGH per assertion-strength rules above).
- It must assert `row.returncode == 0` (proves the captured detail confirms the silent no-op shape).
- It must assert `row.elapsed_ms is not None and row.elapsed_ms < 500` (proves elapsed was captured).

### 5. Updated tests in `test_keep_alive_service.py` / `test_keep_alive_poller.py`

- Each rewritten test still covers real behaviour — not just a syntactic adjustment for `FireResult`. A test that USED to assert `(True, None)` now asserts `result.is_success is True AND result.returncode == 0 AND result.stdout == "..."` (semantic) → good.
- Any test S07 deleted is justified in S07's `notes`. Silent deletion is CRITICAL — the design says do not delete real coverage.

### 6. Dashboard render tests

- Tests live under `tests/dashboard/` (use `client` fixture). A test placed under `tests/unit/` or `tests/integration/` that needs `client` will fail with `fixture 'client' not found` (I-00067) — HIGH.
- The NULL-fallback test inserts a `KeepAliveRun` with explicit `stdout=None` / `elapsed_ms=None` / `returncode=None` (or omits those args, relying on default NULL). Assert the rendered HTML contains `—` for both columns.
- The populated-row test asserts on the specific cell content (`>3500 ms<` or `>3500 ms` anchor) AND the title attribute (`title="OK reply"`). Bare `assert "3500" in html` is MEDIUM (fixable).

### 7. Test isolation

- pytest-randomly is on (per `tests/CLAUDE.md`). Tests MUST be order-independent. Any shared mutable state (module-level dicts mutated by tests, etc.) is HIGH.
- Each test that writes to the DB uses the project's testcontainer fixture; no test writes to port 5433.

### 8. Scope adherence

- S07's `files_changed` contains ONLY test files (and possibly fixture/conftest updates). Any non-test file is a CRITICAL scope violation.

## Test Verification (NON-NEGOTIABLE)

Run:
```bash
uv run pytest \
  tests/unit/test_keep_alive_poller_success_contract.py \
  tests/unit/test_keep_alive_service.py \
  tests/unit/test_keep_alive_poller.py \
  tests/dashboard/test_keep_alive_runs_table.py \
  -v
```

All must pass. Any failure is a CRITICAL finding (the reviewer reproduces what S07 should already have green).

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Missing test from design list, scope violation, silent test deletion, failing test |
| **HIGH** | Wrong mock boundary (fire_claude not subprocess.run), test in wrong directory (client fixture issue), missing time.perf_counter mock |
| **MEDIUM (fixable)** | Shape-only assertions, weak negation, missing semantic anchors |
| **MEDIUM (suggestion)** | Stronger semantic anchors available |
| **LOW** | Nitpicks |

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "I-00112",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "8 passed, 0 failed",
  "notes": ""
}
```

## Lifecycle Commands

```bash
uv run iw step-start I-00112 --step S08
uv run iw step-done I-00112 --step S08 --report ai-dev/active/I-00112/reports/I-00112_S08_CodeReview_report.md
```
