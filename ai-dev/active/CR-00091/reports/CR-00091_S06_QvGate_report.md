# CR-00091 S06 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | migration-check      |
| Command      | `make migration-check` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 12       |

## Output (tail)

```
uv run python scripts/resolve_pending_migration.py
no PENDING migrations found — nothing to do
uv run pytest tests/integration/test_migrations_round_trip.py --timeout=600 -v --no-cov
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00091/.venv/bin/python
cachedir: .pytest_cache
benchmark: 4.0.0 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
hypothesis profile 'default'
Using --randomly-seed=2886384502
rootdir: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00091
configfile: pyproject.toml
plugins: timeout-2.4.0, asyncio-1.3.0, cov-7.1.0, respx-0.22.0, xdist-3.8.0, allure-pytest-2.15.3, Faker-40.13.0, schemathesis-4.19.0, rerunfailures-15.1, benchmark-4.0.0, anyio-4.13.0, hypothesis-6.152.7, randomly-4.1.0
timeout: 600.0s
timeout method: signal
timeout func_only: False
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 5 items

tests/integration/test_migrations_round_trip.py::test_alembic_upgrade_head_succeeds_from_empty PASSED [ 20%]
tests/integration/test_migrations_round_trip.py::test_ac4_resolver_is_noop_on_clean_versions_dir PASSED [ 40%]
tests/integration/test_migrations_round_trip.py::test_alembic_downgrade_base_then_upgrade_head PASSED [ 60%]
tests/integration/test_migrations_round_trip.py::test_alembic_schema_matches_create_all PASSED [ 80%]
tests/integration/test_migrations_round_trip.py::test_resolver_produces_valid_chain_against_real_versions_dir PASSED [100%]

============================== 5 passed in 10.38s ==============================
```

## Verdict

```
pass
```
