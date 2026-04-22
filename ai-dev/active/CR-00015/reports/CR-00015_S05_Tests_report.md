# CR-00015_S05_Tests_report

**Work Item**: CR-00015 — Remove docker-compose db service foot-gun
**Step**: S05
**Agent**: tests-impl

## What was done

Created `tests/integration/test_compose_split.py` with 4 integration tests covering the compose split:

1. `test_root_compose_has_no_db_service` — Verifies the root `docker-compose.yml` has no `db` service
2. `test_bootstrap_compose_has_db_service` — Verifies `docker-compose.bootstrap.yml` has a `db` service with correct image and container name
3. `test_bootstrap_volume_name_stable_across_cwd` — Verifies the volume name (`iw-ai-core_pgdata`) is identical regardless of cwd (exercises the foot-gun scenario)
4. `test_ai_core_db_start_noops_when_db_ready` — Verifies `./ai-core.sh db start` is a no-op when DB is already up (READ-ONLY, no destructive docker ops)

Also added `markers = ["integration: ...]` to `pyproject.toml` to register the `@pytest.mark.integration` marker.

## Files changed

- `tests/integration/test_compose_split.py` — new file, 4 tests
- `pyproject.toml` — added `markers` entry for `integration` mark

## Test results

```
tests/integration/test_compose_split.py::test_root_compose_has_no_db_service PASSED
tests/integration/test_compose_split.py::test_bootstrap_compose_has_db_service PASSED
tests/integration/test_compose_split.py::test_bootstrap_volume_name_stable_across_cwd PASSED
tests/integration/test_compose_split.py::test_ai_core_db_start_noops_when_db_ready PASSED

4 passed in 0.17s
```

All 4 tests pass. `make lint` passes. Tests run cleanly twice in a row (no state leaked).

## Observations

- `docker compose config` reports volumes as `{volume_key: {name: "full_name"}}` — the test reads `volumes[vol_key]["name"]` to get the stable volume name, falling back to the key if `name` is absent (for older compose versions)
- `test_ai_core_db_start_noops_when_db_ready` requires the live DB to be reachable on port 5433 and skips if not (precondition: DB must already be up)
- `test_bootstrap_volume_name_stable_across_cwd` requires docker to be available and skips if not