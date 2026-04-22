# CR-00014_S08_CodeReview_prompt

**Work Item**: CR-00014 — Orchestration DB instance-identity fingerprint
**Step Being Reviewed**: S07 (tests-impl)
**Review Step**: S08

---

## Input Files

- `ai-dev/active/CR-00014/CR-00014_CR_Design.md`
- `ai-dev/active/CR-00014/reports/CR-00014_S07_Tests_report.md`
- All test files listed in the S07 report's `files_changed`
- `tests/CLAUDE.md`, `tests/conftest.py`

## Output Files

- `ai-dev/active/CR-00014/reports/CR-00014_S08_CodeReview_report.md`

## Review Checklist

### 1. Tests fail on pre-change code (negative verification)

A test is only useful if it would fail against the current `main` without this CR's implementation. Pick 2–3 representative tests and verify (mentally or by temporarily stubbing the implementation) that they exercise behavior that didn't exist before. At minimum:

- `test_check_identity_mismatch` — would fail because the module didn't exist.
- `test_dashboard_healthz_identity_503_on_mismatch` — would 404 on main (endpoint doesn't exist).
- `test_daemon_startup_refuses_on_mismatch` — would complete normally on main.

### 2. Testcontainer compliance

- No test connects to port 5433 (grep for `5433`, `localhost:5433`, `IW_CORE_DB_PORT` in test bodies — none should appear).
- psycopg v3 URL replacement present: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` applied after `Base.metadata.create_all()`.
- Each test has isolated state; no test mutates shared global DB state across tests.

### 3. Fixture design

- `identity_matched` / `identity_mismatched` fixtures exist in `tests/conftest.py`, not duplicated in the test files.
- Fixtures use `monkeypatch.setenv` / `monkeypatch.delenv` — NEVER `importlib.reload(orch.config)` (hard rule).
- Session fixtures properly torn down (no leaked connections; rely on existing fixture patterns).

### 4. Assertions are semantic

- `assert match == True` rather than `assert response.status_code == 200` everywhere — both, preferably. The test must fail if JSON shape regresses.
- For error-path tests: assert on the exception *type* AND on key content of the error message (both UUIDs present, for example).
- No `assert True` / `assert response` (shape-only) placeholders.

### 5. Pytest markers & organization

- `@pytest.mark.integration` on every integration test — `make test-unit` must skip them cleanly.
- Unit tests live in `tests/unit/`, integration tests in `tests/integration/`.
- Test names are descriptive: `test_<what>_<condition>_<expected>`.

### 6. Coverage

- `orch/db/identity.py` branch coverage: all four modes (`match`, `mismatch`, `bootstrap`, `missing`) exercised.
- Env-parsing edge cases (empty, whitespace, malformed, uppercase) all have unit tests.
- Migration downgrade/upgrade round trip test present.

### 7. Parallel safety

- If any test uses `monkeypatch` with the same env var, verify they can run in parallel (pytest-xdist) without leaking env state — `monkeypatch` is per-test-function so this should be fine, but check.

### 8. Existing tests still pass

- S07 report should show `make test-integration` running the FULL suite (not just new tests) — verify.
- Any existing test touched (e.g., a daemon-startup fixture now requires the identity env var) is updated explicitly, not accidentally.

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW — standard. Fix in place.

## Subagent Result Contract

Same pattern as S02.

## Lifecycle commands

```bash
uv run iw step-start CR-00014 --step S08
# review + fix ...
uv run iw step-done CR-00014 --step S08 --report ai-dev/active/CR-00014/reports/CR-00014_S08_CodeReview_report.md
```
