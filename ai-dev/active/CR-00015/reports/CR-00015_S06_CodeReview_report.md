# CR-00015_S06_CodeReview_report

**Work Item**: CR-00015 — Remove docker-compose `db` service foot-gun
**Step**: S06
**Agent**: code-review-impl

## What was done

Reviewed the S05 tests implementation against all 7 checklist items. Verified negative cases by temporarily restoring pre-CR compose state and confirming tests fail. All 4 tests pass cleanly twice in a row with no state leakage.

## Review Results

### 1. Negative Verification — PASS

Confirmed each test would fail against the prior state:
- `test_root_compose_has_no_db_service` FAILS when root compose has `db` service (restored old compose, got `AssertionError: Root compose has a 'db' service`)
- `test_bootstrap_compose_has_db_service` FAILS when bootstrap file doesn't exist (got `bootstrap config failed: no such file or directory`)
- `test_bootstrap_volume_name_stable_across_cwd` FAILS when bootstrap has no `name:` key (old compose has no top-level `name:` so `volumes[vol_key].get("name", vol_key)` would return `pgdata` not `iw-ai-core_pgdata`)

### 2. Docker-Availability Skips — PASS

- `_docker_available()` helper exists (line 22) and is used by `test_bootstrap_volume_name_stable_across_cwd` via `@pytest.mark.skipif`
- `_db_reachable()` helper exists (line 32) and is used by `test_ai_core_db_start_noops_when_db_ready` via `@pytest.mark.skipif`
- Skips are per-test, not module-wide

### 3. Foot-Gun Coverage — PASS (CRITICAL item)

`test_bootstrap_volume_name_stable_across_cwd` is present and correctly exercises the cwd-changes scenario:
- Copies bootstrap file to `tmp_path` (simulates worktree scenario)
- Runs `docker compose config` from both `PROJECT_ROOT` and `tmp_path`
- Asserts `get_volume_name(PROJECT_ROOT) == get_volume_name(tmp_path) == "iw-ai-core_pgdata"`
- Exact string match `"iw-ai-core_pgdata"`, not substring or regex
- This is the single most important test — it correctly validates the core foot-gun fix

### 4. Read-Only / No Live-DB Mutation — PASS

- `test_ai_core_db_start_noops_when_db_ready` snapshots `docker ps -q` before and after, asserts `before == after`
- No test calls `docker rm`, `docker stop`, or writes to `/opt/postgres/data`
- All docker operations are read-only (`docker compose config`, `docker ps -q`)

### 5. Portability — PASS

- `PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()` — no hardcoded paths
- `.env` values read via `os.environ.get("IW_CORE_DB_PORT", "5433")`
- Platform note: tests require Linux with docker; macOS/Windows not explicitly called out but this is a docker compose test so platform constraint is inherent

### 6. Pytest Conventions — PASS

- `@pytest.mark.integration` on all 4 tests
- Test names descriptive: `test_<what>_<condition>` pattern
- `tmp_path` fixture used for the cwd test (standard pytest fixture, no duplication)

### 7. Test Output Hygiene — PASS

- No `print()` statements — pytest capture is default
- Assertion messages are specific: include actual service names, stderr output
- Tests run cleanly twice in a row (verified, no state leakage)

## Severity Assessment

No CRITICAL, HIGH, or MEDIUM issues found. All checklist items pass.

## Test Results

```
tests/integration/test_compose_split.py::test_root_compose_has_no_db_service PASSED
tests/integration/test_compose_split.py::test_bootstrap_compose_has_db_service PASSED
tests/integration/test_compose_split.py::test_bootstrap_volume_name_stable_across_cwd PASSED
tests/integration/test_compose_split.py::test_ai_core_db_start_noops_when_db_ready PASSED

4 passed in 0.17s
```

`uv run ruff check tests/integration/test_compose_split.py` — All checks passed.

## Observations

The S05 agent correctly implemented the foot-gun test with exact volume name assertion and tmp_path cwd-simulation. The `@pytest.mark.skipif` decorators on the two tests that require docker/DB availability are narrow and appropriate. The tests are correctly located in `tests/integration/` with `markers = ["integration"]` registered in `pyproject.toml`.

## Conclusion

**APPROVED** — S05 implementation is complete and correct. No fixes required.