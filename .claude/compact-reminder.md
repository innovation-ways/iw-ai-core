# Critical Rules (Survive Compaction)

These rules are NON-NEGOTIABLE and must be followed in every interaction, even after context compaction.

1. **NEVER connect tests to the live database** (port 5433) — use testcontainers only
2. **ALL DB tests use testcontainers** (random Docker port, full isolation)
3. **NEVER call `importlib.reload(orch.config)`** in tests — use `monkeypatch.delenv()` only
4. **After `Base.metadata.create_all()`** in tests, execute `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`
5. **testcontainers returns psycopg2 URLs** — always replace with `psycopg`
6. **SQLAlchemy 2.0 sync ORM** — `Mapped[]` declarative style, psycopg v3, NOT psycopg2
7. **Run `make quality`** before any commit — includes ruff check, ruff format, mypy
8. **Composite PKs**: `(project_id, id)` for work items and batches — always filter by project_id
9. **Append-only tables**: step_runs, fix_cycles, daemon_events — never UPDATE or DELETE
10. **Config via .env only** — never hardcode ports, URLs, or credentials
