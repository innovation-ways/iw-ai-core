# F-00086 S01 — Database Step Report

**Step**: S01 (Database)
**Agent**: database-impl
**Status**: complete

## What was done

Created the `chat_tabs` table that backs the F-00086 multi-tab AI Assistant.

- Added the `ChatTab` ORM model to `orch/db/models.py` under a new
  "Chat Assistant tabs (F-00086)" section, mirroring SQLAlchemy 2.0
  `Mapped[...]` style and the project's reusable `_TIMESTAMPTZ` helper.
- Wrote the Alembic revision `e45b45f74ea0_f_00086_chat_tabs.py`
  (down_revision = `6d78323d0954`, the prior head).

## Schema details

`chat_tabs` columns:

| Column                | Type        | Notes                                                              |
|-----------------------|-------------|--------------------------------------------------------------------|
| `id`                  | UUID        | PK; `server_default gen_random_uuid()` (pgcrypto already enabled). |
| `title`               | TEXT NOT NULL | default `'New chat'`                                              |
| `runtime`             | TEXT NOT NULL | default `'opencode'`; allowlist enforced in `tab_service.py`      |
| `model`               | TEXT NOT NULL |                                                                   |
| `project_id`          | TEXT NOT NULL | FK → `projects(id)` ON DELETE CASCADE                             |
| `opencode_session_id` | TEXT NULL    |                                                                   |
| `status`              | TEXT NOT NULL | default `'active'`; allowlist `{'active','closed'}` in service    |
| `created_at`          | TIMESTAMPTZ NOT NULL | default `now()`                                            |
| `updated_at`          | TIMESTAMPTZ NOT NULL | default `now()`                                            |
| `last_active_at`      | TIMESTAMPTZ NOT NULL | default `now()`                                            |
| `closed_at`           | TIMESTAMPTZ NULL    |                                                             |

Indexes:

- `ix_chat_tabs_status_last_active` on `(status, last_active_at DESC)`
- `ix_chat_tabs_project_status` on `(project_id, status)`
- `uq_chat_tabs_default_per_project` UNIQUE on `(project_id)`
  `WHERE title = 'Default' AND status = 'active'` — race protector for
  the bootstrap_default_tab path (created via raw `op.execute` to match
  the literal text in the spec).

Column comments are set on `runtime`, `status`, `project_id`,
`opencode_session_id`, `closed_at`, and on the table itself
(`Multi-tab AI Assistant chat tabs (F-00086)`).

## Files changed

- `orch/db/models.py` — added `ChatTab` model (uses `uuid.uuid4`
  Python-side default plus `gen_random_uuid()` server default,
  matching the `Evidence` model precedent at line 1042).
- `orch/db/migrations/versions/e45b45f74ea0_f_00086_chat_tabs.py` —
  new revision (`upgrade()` creates table + indexes + partial unique;
  `downgrade()` drops them in reverse order).

## Test results

`make migration-check` (RED then GREEN):

- **RED** (model added, migration not yet written) — one failure in
  `test_alembic_schema_matches_create_all`:

  ```
  AssertionError: Models declare columns that no Alembic migration creates:
      chat_tabs.closed_at
      chat_tabs.created_at
      chat_tabs.id
      chat_tabs.last_active_at
      chat_tabs.model
      chat_tabs.opencode_session_id
      chat_tabs.project_id
      chat_tabs.runtime
      chat_tabs.status
      chat_tabs.title
      chat_tabs.updated_at
  ```

- **GREEN** (after writing the revision):

  ```
  tests/integration/test_migrations_round_trip.py::test_alembic_upgrade_head_succeeds_from_empty PASSED
  tests/integration/test_migrations_round_trip.py::test_alembic_schema_matches_create_all PASSED
  tests/integration/test_migrations_round_trip.py::test_alembic_downgrade_base_then_upgrade_head PASSED
  3 passed in 9.52s
  ```

  The round-trip test covers `upgrade head` from base, `Base.metadata.create_all()`
  schema parity, and `downgrade base → upgrade head` — all green.

## Other quality gates

- `make format` — `777 files already formatted`
- `make typecheck` — `Success: no issues found in 258 source files`
- `make lint` — `All checks passed!`

## Observations

- Chose `gen_random_uuid()` as the server default (with `uuid.uuid4` as
  the Python-side default for in-memory inserts) because `pgcrypto` is
  enabled by the earlier `2bd86f8c105c_add_iw_core_instance` revision
  and the `Evidence` model already uses this exact pattern.
- Used `op.execute("CREATE UNIQUE INDEX ...")` for the partial unique
  index per the literal text the prompt suggested; this matches the
  precedent in F-00077 (chat conversations), which uses
  `create_index(..., unique=True, postgresql_where=...)` for one
  partial unique and `op.execute` for another DDL fragment. Either form
  round-trips cleanly through `make migration-check`.
- No CHECK constraints on `runtime` or `status` — allowlist enforcement
  is deferred to `orch/chat/tab_service.py` (S03), matching CR-00062's
  `cli_tool` pattern so adding the `pi` runtime in F-B will be a code
  change, not a migration.
