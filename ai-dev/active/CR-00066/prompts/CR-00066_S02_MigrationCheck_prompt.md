# CR-00066_S02_MigrationCheck_prompt

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Step**: S02
**Agent**: qv-gate
**Gate**: migration-check
**Command**: make migration-check

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Task

```bash
make migration-check
```

Runs the Alembic round-trip test: upgrade-from-base, schema parity vs `Base.metadata.create_all()`, downgrade-then-upgrade. Verifies the 3 new columns and seed UPDATE from S01 are correct.

## Pass Criteria

Exit code 0.

## Subagent Result Contract

```bash
uv run iw step-done CR-00066 --step S02
# or on failure:
uv run iw step-fail CR-00066 --step S02 --reason "<details>"
```
