# CR-00025 S04 — Code review of S03 (tests)

**Work Item**: CR-00025 — Implement missing evidence-ingestion pipeline (CR-00020 follow-up) and backfill archived items
**Step**: S04
**Agent**: code-review-impl
**Reviewing**: S03 (tests-impl)

---

## ⛔ Docker is off-limits

Same constraints as S01.

## Input Files

- `uv run iw item-status CR-00025 --json`
- `ai-dev/active/CR-00025/CR-00025_CR_Design.md` (read AC1–AC5)
- `ai-dev/active/CR-00025/reports/CR-00025_S03_Tests_report.md`
- `tests/unit/test_evidences_ingest.py`
- `tests/integration/test_evidences_lifecycle.py`
- `tests/CLAUDE.md`
- `tests/conftest.py`

## Output Files

- `ai-dev/active/CR-00025/reports/CR-00025_S04_CodeReview_Tests_report.md`

## Context

The historical context: CR-00020's S15 qv-browser was supposed to verify
post-archive evidence visibility but didn't, so the bug shipped to
production. The regression test added in S03 exists specifically to
prevent this. **You must verify that test actually exercises the
archiver's cleanup path.**

## Review Checklist

### 1. Acceptance criteria coverage

Walk through AC1–AC5 in the design doc. For each AC, identify exactly
which test function asserts it. If any AC has no corresponding test,
that's a HIGH finding.

### 2. The post-archive regression test (CRITICAL focus)

- Does the test actually call `archive_work_item(..., cleanup=True)`
  rather than simulating cleanup with `shutil.rmtree`? It must use the
  real archiver to catch regressions in archiver behaviour.
- Does the test verify `ai-dev/active/<id>/` is gone after the call,
  before asserting `_list_evidences` works?
- Does it assert byte-identical content for every evidence file (not
  just row count)? Per AC5, the dashboard must serve the same bytes.
- Does the docstring explicitly call out that this guards against the
  CR-00020 production bug? (Soft requirement — improves
  archaeology when the test fails years from now.)

### 3. Testcontainer compliance

- No live DB connections on port 5433. Search for `5433` in the test
  files — should appear zero times.
- No `importlib.reload(orch.config)` calls.
- `monkeypatch.setenv` / `monkeypatch.delenv` used for env-var changes.
- psycopg URL replacement (`postgresql+psycopg2://` →
  `postgresql+psycopg://`) handled by the fixture, not bypassed.

### 4. No DB mocking in integration tests

- Search for `Mock(`, `MagicMock`, `patch(`, `mocker.` in the integration
  test file. The DB layer must not be mocked.

### 5. CLI tests use real `CliRunner`

- The integration tests must invoke `iw approve` and `iw step-done` via
  Click's `CliRunner` against the real command groups, not via direct
  function calls that bypass the CLI machinery (which would skip the
  `output_error` exit-code handling needed for AC4).

### 6. Idempotency test (AC3)

- The upsert-overwrite test must verify (a) row count stays at 1,
  (b) content matches the NEW bytes, and (c) `step_id` is updated
  when re-ingesting with a different step_id.

### 7. Hard-fail test (AC4)

- The oversize test must verify the **transaction rolled back**, not
  just that an exception was raised. The work item status must remain
  `draft`. Reject if the test only asserts the raise.

### 8. Fixture isolation

- Each test creates its own work item ID (e.g. via `uuid` or counter)
  to avoid cross-test contamination.
- `tmp_path` is used for the active dir; no writes to the real
  `ai-dev/` tree during tests.

### 9. Missing edge cases (HIGH if absent)

- Empty dir
- Missing dir
- Subdir / symlink in phase dir (skipped)
- Unknown extension default MIME
- YAML extension MIME registration

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — the new unit tests must pass.
2. `make test-integration` — the new integration tests must pass.
3. `make lint`, `make typecheck`, `make format-check` — green.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Missing AC test, broken testcontainer, DB mocking | Must fix |
| **HIGH** | Missing edge case, non-deterministic test | Must fix |
| **MEDIUM (fixable)** | Quality issue, weak assertion | Should fix |
| **MEDIUM (suggestion)** | Better assertion pattern | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00025",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit + Y integration passed, 0 failed",
  "notes": ""
}
```
