# CR-00065 S02 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | migration-check      |
| Command      | `make migration-check` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 10       |

## Output (tail)

```
uv run pytest tests/integration/test_migrations_round_trip.py -v --no-cov
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00065/.venv/bin/python
cachedir: .pytest_cache
hypothesis profile 'default'
Using --randomly-seed=2837507947
rootdir: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00065
configfile: pyproject.toml
plugins: timeout-2.4.0, asyncio-1.3.0, cov-7.1.0, respx-0.22.0, xdist-3.8.0, allure-pytest-2.15.3, Faker-40.13.0, rerunfailures-15.1, anyio-4.13.0, hypothesis-6.152.7, randomly-4.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 3 items

tests/integration/test_migrations_round_trip.py::test_alembic_schema_matches_create_all PASSED [ 33%]
tests/integration/test_migrations_round_trip.py::test_alembic_downgrade_base_then_upgrade_head PASSED [ 66%]
tests/integration/test_migrations_round_trip.py::test_alembic_upgrade_head_succeeds_from_empty PASSED [100%]

============================== 3 passed in 8.79s ===============================
```

## Verdict

```
pass
```
