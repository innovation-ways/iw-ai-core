# I-00112_S07_Tests_prompt

**Work Item**: I-00112 -- Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires
**Step**: S07
**Agent**: Tests

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers spun up by pytest fixtures (with `@pytest.mark.integration` or under `tests/integration/`) are the only exception. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch migrations. Tests that need the schema use the testcontainer fixtures, which run alembic upgrade head as part of fixture setup — that is allowed.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00112 --json`.
- `ai-dev/active/I-00112/I-00112_Issue_Design.md` — design document. The **Test to Reproduce** section gives you the canonical test file body to author verbatim.
- `orch/keep_alive_service.py` — post-S03 (`FireResult` + new `log_run` signature).
- `orch/daemon/keep_alive_poller.py` — post-S03 (success-contract enforcement).
- `tests/unit/test_keep_alive_service.py` — existing service tests (likely broken by S03's signature change; you fix them here).
- `tests/unit/test_keep_alive_poller.py` — existing poller tests (likely broken; you fix them here).
- `tests/integration/test_keep_alive_poller_integration.py` — existing integration test (likely still passes if it mocks at the `fire_claude` boundary; verify).
- `tests/CLAUDE.md` — test conventions (fixtures, naming, isolation).
- `skills/iw-ai-core-testing/SKILL.md` — assertion strength, RED-flag checklist.

## Output Files

- `tests/unit/test_keep_alive_poller_success_contract.py` — NEW file with the six reproduction + regression tests from the design's **Test to Reproduce** section.
- `tests/unit/test_keep_alive_service.py` — UPDATED to match S03's new `FireResult` return shape (rewrite the assertions; do not delete tests that still cover real behaviour).
- `tests/unit/test_keep_alive_poller.py` — UPDATED for the same reason.
- `tests/dashboard/test_keep_alive_runs_table.py` — NEW or extended: render the recent-runs fragment with NULL elapsed/stdout and with populated values; assert the cell text is `—` and the populated values respectively. (Create if no equivalent file exists; extend if a `test_keep_alive_*` file already lives under `tests/dashboard/`.)
- `ai-dev/active/I-00112/reports/I-00112_S07_Tests_report.md` — step report.

## Context

S01 added the schema. S03 made the daemon capture the new fields and enforce the success contract. S05 surfaced them on the dashboard. Your step writes the tests that PROVE the bug is gone and STAY in the suite to prevent regression. Tests MUST exercise the actual success-contract decision boundary (`subprocess.run` mock), not just shape-check the `fire_claude` wrapper.

Read `ai-dev/active/I-00112/I-00112_Issue_Design.md` first — the **Test to Reproduce** section gives you the exact file body. Read `tests/CLAUDE.md` and the iw-ai-core-testing skill for assertion strength rules.

## Requirements

### 1. Create `tests/unit/test_keep_alive_poller_success_contract.py`

Author the six tests verbatim from the design doc's **Test to Reproduce** section. They are:

1. `test_i00112_silent_no_op_is_not_success_empty_stdout` — rc=0 + empty stdout + ~0 ms → `is_success is False`.
2. `test_i00112_silent_no_op_is_not_success_fast_elapsed` — rc=0 + non-empty stdout + <500 ms → `is_success is False`.
3. `test_i00112_real_round_trip_is_success` — rc=0 + non-empty stdout + >=500 ms → `is_success is True`.
4. `test_i00112_nonzero_returncode_is_failure` — rc≠0 + anything → `is_success is False`.
5. `test_i00112_poller_persists_captured_fields` — `KeepAlivePoller.poll()` writes a row with all four diagnostic fields populated AND `status='success'`.
6. `test_i00112_poller_logs_failed_when_contract_violated` — silent no-op → `status in ('failed', 'retried_failed')`, NOT `'success'`. This is the canonical reproduction — the test that would have caught the 05:00 2026-05-25 incident.

Implementation notes:
- **Mock at the `subprocess.run` boundary.** This is what makes the test catch the bug class; mocking at `fire_claude` (the wrapper) would re-introduce the same blind spot the bug exploits. Patch `orch.keep_alive_service.subprocess.run`.
- **Mock `time.perf_counter`** with a `side_effect=[start, end]` pair so elapsed_ms is deterministic. Tests 1, 2, 4, 6 use a short delta; test 3 and 5 use a delta ≥ 0.5 s.
- **Tests 5 and 6** also need a `KeepAliveSlot` row in the DB so the poller has something to fire — use the project's testcontainer DB fixture (`db_session` or equivalent — read `tests/conftest.py` to find the right fixture name; under `tests/dashboard/` it's `db`, under `tests/unit/` and `tests/integration/` it may be `db_session` or `session`). If no unit-level DB fixture exists, move tests 5 and 6 to `tests/integration/test_keep_alive_poller_success_contract.py` and keep 1–4 under `tests/unit/`.
- **Slot fixture**: insert one row with `time_hhmm=<now formatted as HH:MM>`, `enabled=True`, `config_id=1`. Also ensure a `KeepAliveConfig` row exists at `id=1` (the `get_config` helper creates it if missing).
- **Mock both attempts identically for test 6** — the retry uses a new message but the same subprocess mock, so a single `return_value=fake` works for both calls if the mock is not exhausted.
- Use `pytest.mark.parametrize` if you find yourself copy-pasting two near-identical bodies; the design's six tests are distinct enough that parametrization is optional.

### 2. Update `tests/unit/test_keep_alive_service.py` to match S03's `FireResult`

S03's change broke any test that asserted on `fire_claude`'s `(bool, error)` tuple shape. Rewrite each broken test to assert on `FireResult` fields:

- `result.is_success` instead of the bool.
- `result.returncode`, `result.stdout`, `result.stderr`, `result.elapsed_ms` for the detail.
- If the original test was only checking "rc=0 → True / rc!=0 → False" (the OLD contract), expand it to check the FULL three-part contract — this is the entire point of S07's coverage strengthening.

Do NOT delete any test that covered real behaviour. If a test is genuinely redundant with the new file (`test_keep_alive_poller_success_contract.py`), mark it for deletion in your `notes` with a one-line justification; do not silently delete.

### 3. Update `tests/unit/test_keep_alive_poller.py` similarly

Any test mocking `fire_claude` to return `(True, None)` / `(False, "…")` must now mock it to return `FireResult(...)`. Construct realistic FireResult instances (`FireResult(returncode=0, stdout="OK", stderr="", elapsed_ms=3000)`).

### 4. Dashboard render test

Create or extend `tests/dashboard/test_keep_alive_runs_table.py`. The file MUST use the `client` fixture (only available under `tests/dashboard/` — see I-00067).

Two test cases:

```python
def test_recent_runs_table_renders_em_dash_for_null_diagnostic_fields(client, db):
    """I-00112: pre-fix rows (NULL stdout/elapsed_ms) render as '—' without crashing."""
    # Arrange: insert a legacy-shape KeepAliveRun with NULL stdout/elapsed_ms/returncode
    db.add(KeepAliveRun(slot_id=None, slot_time="05:00", status="success", error=None))
    db.commit()
    # Act
    resp = client.get("/api/keep-alive/runs")
    # Assert: semantic content, not just shape
    assert resp.status_code == 200
    html = resp.text
    assert ">Elapsed<" in html, "table must have Elapsed column header"
    assert ">Output<" in html, "table must have Output column header"
    assert "—" in html, "NULL diagnostic fields must render as em-dash"


def test_recent_runs_table_renders_populated_diagnostic_fields(client, db):
    """I-00112: post-fix rows render elapsed_ms and stdout snippet."""
    db.add(KeepAliveRun(
        slot_id=None, slot_time="05:00", status="success", error=None,
        stdout="OK reply", stderr="", elapsed_ms=3500, returncode=0,
    ))
    db.commit()
    resp = client.get("/api/keep-alive/runs")
    assert resp.status_code == 200
    html = resp.text
    assert "3500 ms" in html, "elapsed_ms must render with unit"
    # title attribute carries the full stdout for hover
    assert 'title="OK reply"' in html, "stdout must populate title for hover"
    # cell body shows the snippet
    assert ">OK reply" in html, "stdout snippet must appear in the cell"
```

If you cannot get the `KeepAliveRun` import path right from your worktree, read `orch/db/models.py` to find the canonical import.

### 5. Assertion strength

Read `skills/iw-ai-core-testing/SKILL.md` before writing assertions. Concretely:

- Assert SPECIFIC values, not shape. `assert "—" in html` is OK because `—` is the literal symbol the template emits. `assert "Elapsed" in html` is shape; `assert ">Elapsed<" in html` is closer to semantic (anchors on the column header location).
- Forbidden patterns (per I003 lesson, see warning below): `assert "permissions" in data`, `assert len(data) > 0`.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For I-00112 specifically:
- BAD: `assert "Elapsed" in html` (only verifies the word appears — could be in a comment)
- GOOD: `assert ">Elapsed<" in html` (verifies it appears between tags — column header location)
- BAD: `assert row.status != "success"` (only rules out one value)
- GOOD: `assert row.status in ("failed", "retried_failed")` (asserts the specific expected values)

### 6. Do NOT touch any non-test file

- **Do NOT** modify `orch/`, `dashboard/`, or any production code.
- **Do NOT** touch the migration or models.
- **Do NOT** revert S01/S03/S05 work to "demonstrate RED" — that is a thrash-prone operation explicitly forbidden by this template. S03 already captured RED evidence by running the existing broken tests; S07 documents per-test pre-S03 failure reasoning in `notes`.

If you find yourself reaching for production code, STOP — that work belongs to an upstream step (or is already done).

## Project Conventions

Read `tests/CLAUDE.md` for:
- Fixture names (`db`, `db_session`, `client`).
- pytest-randomly is on — every test MUST be order-independent.
- Live-DB write guard — testcontainer fixtures only (see CLAUDE.md root, the 2026-04-22 incident).
- psycopg URL replacement: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")` after testcontainer.

Read `skills/iw-ai-core-testing/SKILL.md` for the RED-flag checklist.

## TDD Requirement

S07 is a dedicated coverage step — RED-exempt by template policy. Use:
```
tdd_red_evidence: "n/a — dedicated coverage step; behavioural RED owned by S03 (existing tests broken by FireResult signature change). Per-test pre-S03 failure reasoning recorded in notes."
```

In the `notes` field, briefly note for each NEW test what pre-S03 behaviour it would have asserted (and how that assertion would have caught the silent no-op).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — zero errors. Test files are typechecked too — pay attention to mock typings.
3. **`make lint`** — zero errors. `tests/` is included in the lint pass.

## Test Verification (NON-NEGOTIABLE)

Run only the test files you wrote or modified:

```bash
uv run pytest \
  tests/unit/test_keep_alive_poller_success_contract.py \
  tests/unit/test_keep_alive_service.py \
  tests/unit/test_keep_alive_poller.py \
  tests/dashboard/test_keep_alive_runs_table.py \
  -v
```

ALL must pass. Do NOT run `make test-unit`, `make test-integration`, `make test-frontend`, or `make allure-integration` — those are S16/S17 downstream gates.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "Tests",
  "work_item": "I-00112",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_keep_alive_poller_success_contract.py",
    "tests/unit/test_keep_alive_service.py",
    "tests/unit/test_keep_alive_poller.py",
    "tests/dashboard/test_keep_alive_runs_table.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "8 passed, 0 failed (6 success-contract + 2 dashboard-render)",
  "tdd_red_evidence": "n/a — dedicated coverage step; behavioural RED owned by S03. Per-test pre-S03 reasoning in notes.",
  "blockers": [],
  "notes": "Per-test pre-S03 reasoning: test 1 would have asserted is_success==False against pre-S03 code that returned (True, None) on rc=0 + empty stdout — the existing tuple shape did not expose enough information to make the assertion at all, which is itself the bug. Tests 5+6 were placed under tests/unit/ because the project's `db_session` fixture is unit-suite-compatible; verify <project>/tests/conftest.py."
}
```

## Lifecycle Commands

```bash
uv run iw step-start I-00112 --step S07
mkdir -p ai-dev/active/I-00112/reports
uv run iw step-done I-00112 --step S07 --report ai-dev/active/I-00112/reports/I-00112_S07_Tests_report.md
```
