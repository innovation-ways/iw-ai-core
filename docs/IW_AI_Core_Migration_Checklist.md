# IW AI Core — Migration Checklist

**Project**: IW AI Core (Innovation Ways AI Orchestration Platform)
**Author**: Sergio G. + Claude
**Date**: 2026-04-22
**Version**: 2.0.0
**Status**: Draft

---

## 1. Overview

This checklist covers the workflow for agents writing database migrations in the
IW AI Core system. The key contract: **agents write migration files, the daemon
applies them**.

---

## 2. Agent Migration Workflow

When your step is a Database step and you need to change the schema:

### 2.1. Write the Migration File

Generate the migration file using Alembic (file-write only — no DB touched):

```bash
uv run alembic revision --autogenerate -m "add user preferences table"
```

This creates `orch/db/migrations/versions/<revision>_add_user_preferences_table.py`.

Review the generated migration:
- Correct table name, columns, types
- Indexes and constraints match the design
- `down_revision` points to the correct parent
- No unintended column drops or data loss

### 2.2. Write the Integration Test

Write a test under `tests/integration/` that exercises the migration against
a testcontainer. This is the one place agents MAY run migrations against a
real PostgreSQL — but it's a throwaway testcontainer, not the live DB.

```python
def test_user_preferences_crud(db_session):
    # Create preference
    pref = UserPreference(project_id="test", key="theme", value="dark")
    db_session.add(pref)
    db_session.commit()
    # Read it back
    stored = db_session.get(UserPreference, pref.id)
    assert stored.value == "dark"
```

Run it:
```bash
make test-integration
```

If the test fails, fix the migration file (step 2.1) and repeat. Do not proceed
until the test passes.

### 2.3. Commit & Push

Commit the migration file and the test in your worktree branch:

```bash
git add orch/db/migrations/versions/<revision>.py tests/integration/test_user_preferences.py
git commit -m "add user preferences table for CR-00017"
git push
```

### 2.4. Do NOT run `alembic upgrade head`

**STOP here.** Do not run `alembic upgrade head` against the live orchestration DB.
The daemon handles the rest of the pipeline:

```
Phase 1 (pre-merge):  daemon dry-runs migration against a fresh testcontainer
                      → if fails, batch is marked MIGRATION_INVALID, fix-cycle triggers
Phase 2 (post-merge): daemon applies migration to live DB (port 5433)
                      → if fails, auto-rollback is attempted
Phase 3 (rollback):   if Phase 2 rollback fails, merge queue is frozen
                      → human operator intervenes
```

### 2.5. Monitor

Watch the dashboard's batch detail view for `pending_migration_log` entries.
The daemon logs each phase outcome there. If Phase 1 fails, you'll see the error
before the merge is even attempted.

---

## 3. For Operators

If you need to inspect or apply migrations manually:

```bash
# List pending migrations (safe — read-only)
uv run iw migrations list-pending

# Dry-run against testcontainer (safe)
uv run iw migrations dry-run

# Apply to live DB (requires confirmation, refuses if IW_CORE_AGENT_CONTEXT=true)
uv run iw migrations apply --i-am-operator

# Alternative entry points (always available to operators)
./ai-core.sh db migrate
make db-migrate
```

---

## 4. Policy

See [`docs/IW_AI_Core_Agent_Constraints.md`](docs/IW_AI_Core_Agent_Constraints.md) (R2)
for the full rules around migrations.

See [`docs/IW_AI_Core_Tech_Stack.md`](docs/IW_AI_Core_Tech_Stack.md) for the
3-phase merge pipeline diagram.