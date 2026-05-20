# CR-00066_S09_QvGate_prompt

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Step**: S09
**Agent**: qv-gate
**Gate**: integration-tests
**Command**: make test-integration

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## Task

```bash
make test-integration
```

Runs `tests/integration/` and `tests/dashboard/` including `test_context_tokens_migration.py` added in S01 and `test_step_monitor_token_poll.py` added in S03.

## Pass Criteria

Exit code 0.

## Subagent Result Contract

```bash
uv run iw step-done CR-00066 --step S09
# or:
uv run iw step-fail CR-00066 --step S09 --reason "<details>"
```
