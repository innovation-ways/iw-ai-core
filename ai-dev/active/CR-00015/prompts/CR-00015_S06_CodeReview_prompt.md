# CR-00015_S06_CodeReview_prompt

**Work Item**: CR-00015 — Remove docker-compose db service foot-gun
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/CR-00015/CR-00015_CR_Design.md`
- `ai-dev/active/CR-00015/reports/CR-00015_S05_Tests_report.md`
- `tests/integration/test_compose_split.py`
- `tests/CLAUDE.md`, `tests/conftest.py`

## Output Files

- `ai-dev/active/CR-00015/reports/CR-00015_S06_CodeReview_report.md`

## Review Checklist

### 1. Negative verification — tests fail on pre-CR code

Confirm the S05 report documents that the tests would fail against the prior state:
- `test_root_compose_has_no_db_service` would FAIL because the pre-CR root compose file had `db`.
- `test_bootstrap_compose_has_db_service` would FAIL because the file didn't exist.
- `test_bootstrap_volume_name_stable_across_cwd` would FAIL because the previous file had no `name:` key.

If the S05 agent didn't verify this, flag HIGH and have them do so.

### 2. Docker-availability skips

- `_docker_available` / `_db_reachable` helpers exist OR the tests have inline skipifs.
- Tests skip gracefully when docker is unavailable (CI without docker should see skipped, not failed).
- Skips are narrow (per-test), not module-wide.

### 3. Foot-gun coverage

- `test_bootstrap_volume_name_stable_across_cwd` is present and actually exercises the cwd-changes scenario (copies the file to a tmp dir, runs compose from there).
- It asserts the volume name is exactly `iw-ai-core_pgdata` — not a substring match, not a regex.
- This is the single most important test in the suite. If it's missing or weak, CRITICAL.

### 4. Read-only / no live-DB mutation

- No test stops, removes, or modifies the live `postgres` container.
- No test writes to `/opt/postgres/data`.
- `test_ai_core_db_start_noops_when_db_ready` is read-only (checks container count before/after; they must be equal).

### 5. Portability

- Tests use `PROJECT_ROOT` resolved from `__file__`, not hardcoded paths.
- `.env` values are read via `os.environ.get(..., default)`, not assumed.
- Platform assumptions documented (Linux with docker — note any macOS / Windows caveats).

### 6. Pytest conventions

- `@pytest.mark.integration` on every test.
- Test names descriptive: `test_<what>_<condition>`.
- Fixture reuse — no duplicated setup.

### 7. Test output hygiene

- Tests run cleanly twice in a row (no state leaked into the env / containers).
- No `print()` leaks — use pytest's built-in capture.
- Assertion messages are specific (include actual values on failure, not just `assert x`).

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW — standard. Fix in place.

## Subagent Result Contract

Same pattern as prior S02/S04/S06 reviews.

## Lifecycle commands

```bash
uv run iw step-start CR-00015 --step S06
# review + fix ...
uv run iw step-done CR-00015 --step S06 --report ai-dev/active/CR-00015/reports/CR-00015_S06_CodeReview_report.md
```
