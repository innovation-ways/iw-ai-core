# CR-00065_S02_MigrationCheck_prompt

**Work Item**: CR-00065 — Live Agent Session Log Viewer
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

Run the migration round-trip quality gate to verify the Alembic migration introduced in S01 is correct.

```bash
make migration-check
```

This gate runs `tests/integration/test_migrations_round_trip.py` against a fresh testcontainer:
1. Upgrade from base to head
2. Schema parity check: `alembic upgrade head` + `Base.metadata.create_all()` must produce identical tables
3. Downgrade then upgrade round-trip

## Pass Criteria

Exit code 0 from `make migration-check`.

## Subagent Result Contract

```bash
# On pass
uv run iw step-done CR-00065 --step S02

# On failure
uv run iw step-fail CR-00065 --step S02 --reason "<gate failure details>"
```
