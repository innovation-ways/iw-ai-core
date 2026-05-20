# CR-00065_S10_QvGate_prompt

**Work Item**: CR-00065 — Live Agent Session Log Viewer
**Step**: S10
**Agent**: qv-gate
**Gate**: integration-tests
**Command**: make test-integration

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Task

Run the full integration test suite:

```bash
make test-integration
```

This runs `tests/integration/` and `tests/dashboard/` against a PostgreSQL testcontainer (including the new `test_step_run_session_file.py` and `test_items_session_log.py` added in S03/S04).

## Pass Criteria

Exit code 0 from `make test-integration`.

## Subagent Result Contract

```bash
# On pass
uv run iw step-done CR-00065 --step S10

# On failure
uv run iw step-fail CR-00065 --step S10 --reason "<failure details>"
```
