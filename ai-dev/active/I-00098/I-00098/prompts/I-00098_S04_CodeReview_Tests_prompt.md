# I-00098_S04_CodeReview_Tests_prompt

**Work Item**: I-00098 -- Keep-alive scheduler re-fires successful slots around UTC midnight (TZ mismatch in `get_due_slots`)
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection is allowed; testcontainers via pytest fixtures are allowed.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migration touched by this item.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00098 --json`
- `ai-dev/active/I-00098/I-00098_Issue_Design.md`
- `ai-dev/active/I-00098/reports/I-00098_S03_Tests_report.md`
- `tests/integration/test_keep_alive_integration.py` (post-S03)
- `tests/CLAUDE.md` — testing rules
- `skills/iw-ai-core-testing/SKILL.md` — assertion-strength rules

## Output Files

- `ai-dev/active/I-00098/reports/I-00098_S04_CodeReview_report.md`

## Context

You are reviewing S03's tests for the keep-alive TZ-mismatch fix. The tests must (a) be reproducible across `pytest-randomly` seeds, (b) actually exercise the bug at the SQL level (not just at the mock level), and (c) cover multiple local-TZ offsets.

## Read the Design Document FIRST

Anchor on:

- **AC1** — bug fixed in the mismatch window.
- **AC2** — regression test exists; the named test in TDD Approach is `test_get_due_slots_skips_already_run_slot_across_utc_midnight`. **If this test is missing from `files_changed`, that's CRITICAL.**
- **AC3** — non-regression in the UTC case.
- **TDD Approach** — integration tests in `tests/integration/test_keep_alive_integration.py`; no new unit tests.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
uv run ruff check tests/integration/test_keep_alive_integration.py
uv run ruff format --check tests/integration/test_keep_alive_integration.py
```

NEW violations → CRITICAL findings (`category: "conventions"`).

## Review Checklist

### 1. Bug-Exposing Test Present and Plausible (CRITICAL)

- The test named in the design (AC2 + TDD section) MUST exist in `tests/integration/test_keep_alive_integration.py`. If absent → CRITICAL.
- The test MUST use the testcontainer-backed `db_session` fixture, not a `MagicMock` DB. A mocked DB cannot reproduce the bug — flag CRITICAL.
- The test MUST use `freezegun.freeze_time` to pin to a local-midnight UTC-mismatch instant. Without freezing, the test is wall-clock-dependent and will flake — flag HIGH.
- The test MUST seed `fired_at` to a **deterministic earlier-today-local / yesterday-UTC `TIMESTAMPTZ` instant** (e.g., `2026-05-17 23:30 UTC` for a +01:00 host with local frozen at `2026-05-18 00:30`). The accepted mechanism: call `log_run()` (which writes via the server default `func.now()` — the production path) and then issue an explicit `UPDATE keep_alive_runs SET fired_at = :ts WHERE id = :run_id` to the chosen instant. **Leaving `fired_at` as bare `func.now()` is the actual flake source** — `func.now()` is server-side, `freezegun` cannot freeze it, and on most CI clocks the resulting `func.date(fired_at)` matches the frozen `today_date`, the pre-fix filter matches, the slot is correctly skipped, and the test passes against pre-fix code (no RED, bug not reproduced). If the test leaves `fired_at` as bare `func.now()`, flag HIGH.
- The test MUST assert on a **specific value**: `assert get_due_slots(db_session) == []`. Shape-only assertions (`assert isinstance(... , list)`, `assert len(...) < 2`) → MEDIUM_FIXABLE.

### 2. TZ-Offset Parametrized Coverage (HIGH)

- At least UTC + one non-UTC offset MUST be present. (Design calls for UTC, +01:00, +02:00, -05:00; if some were dropped per the design's "if you can't make it reliable" clause, the report's `notes` must explain which and why. If the explanation is absent, MEDIUM_FIXABLE.)
- The UTC control case is a non-regression smoke; if missing, MEDIUM (suggestion).
- If parametrize is implemented via `monkeypatch.setenv("TZ", ...)` + `time.tzset()`, verify the teardown restores the prior TZ — env-var leakage across tests is HIGH.

### 3. Test Isolation Under pytest-randomly

- Report should mention "verified under randomly-seed=X and Y" in `tdd_red_evidence` or `notes`. If absent, MEDIUM_FIXABLE.
- Look for shared module-level state across tests in the file (constants are fine; mutable fixtures are not).
- No `importlib.reload(orch.config)`. No `addopts -p no:randomly`. Either → CRITICAL.
- Tests must not depend on each other's ordering.

### 4. RED Evidence

- `tdd_red_evidence` in S03's report should reason about pre-fix behaviour for each new test. The bug-exposing test should describe the pre-fix failure mode. Non-regression controls (UTC) explicitly stating "would have passed pre-fix — non-regression control" is acceptable per the design's guidance.
- If the evidence is just `"X passed"` or a copy-paste of `test_summary`, that's MEDIUM_FIXABLE (skill §0 requires reasoning about whether the test could fail).

### 5. Scope Adherence

- `files_changed` must be only `tests/integration/test_keep_alive_integration.py`. Production code edits → CRITICAL.
- Do NOT accept touching `tests/integration/test_keep_alive_poller_integration.py` — that's I-00090's territory and is unrelated.

### 6. Project Conventions

- Imports: grouped per ruff isort rules; `freezegun` at top of third-party block; new `pytest` imports merged with existing.
- Test names: snake_case starting with `test_`, describing behaviour.

## Test Verification

```bash
uv run pytest tests/integration/test_keep_alive_integration.py -v --no-cov
uv run pytest tests/integration/test_keep_alive_integration.py --randomly-seed=12345 --no-cov -q
uv run pytest tests/integration/test_keep_alive_integration.py --randomly-seed=67890 --no-cov -q
```

All three runs must be green. A failure on one seed but not another = order dependence → HIGH.

## Severity Levels

Standard table.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00098",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (verified under 2 randomly seeds)",
  "notes": ""
}
```
