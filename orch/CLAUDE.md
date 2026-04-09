# orch/ — Core Python Package

IW AI Core's orchestration engine: ORM models, CLI, daemon, archive, and skills sync.

## Package Structure

| Subpackage | Purpose |
|------------|---------|
| `config.py` | `load_config()` / `get_db_url()` — reads `.env`, fails fast on missing vars |
| `db/models.py` | All 10 SQLAlchemy 2.0 ORM models + `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` constants |
| `db/session.py` | `engine`, `SessionLocal`, `get_session()` context manager |
| `db/migrations/` | Alembic versions — `env.py` imports `Base` from `orch.db.models` |
| `cli/` | Click command groups — agent-to-DB bridge |
| `daemon/` | Polling loop, worktree launch, fix cycles, merge queue |
| `archive/` | Two-tier archive (DB TEXT + zstd `.tar.zst`) |
| `skills/` | Skill sync engine — copies master skills to project worktrees |
| `utils/log_capture.py` | Step log capture utilities |

## Database Layer

**10 tables**, all scoped by `project_id` for multi-project isolation.

Key tables:
- `work_items` — Features, Issues, ChangeRequests with composite PK `(project_id, id)`
- `step_runs` / `fix_cycles` / `daemon_events` — append-only audit tables (never UPDATE)
- `id_sequences` — atomic sequential ID allocation via `SELECT FOR UPDATE`

**ENUMs** (10): `work_item_type`, `work_item_status`, `work_item_phase`, `step_type`, `step_status`, `run_status`, `fix_trigger`, `fix_status`, `batch_status`, `batch_item_status`.

**FTS**: `work_items.design_doc_search` (TSVECTOR) updated by `trg_work_items_fts` — raw DDL, not captured by `create_all()`. See `tests/CLAUDE.md`.

**Gotcha**: `DaemonEvent.metadata` → `event_metadata` in Python. SQLAlchemy reserves `metadata` on `DeclarativeBase` subclasses. DB column is still `metadata`.

## CLI Command Groups (`orch/cli/`)

Entry point: `iw` (defined in `pyproject.toml`). Composed from:

| Module | Commands |
|--------|----------|
| `id_commands.py` | `next-id`, `current-project` |
| `project_commands.py` | `register`, `projects list` |
| `item_commands.py` | `approve`, `item-status` |
| `step_commands.py` | `step-start`, `step-done`, `step-fail` |
| `batch_commands.py` | `batch-create`, `batch-approve`, `batch-status`, `batch-pause`, `batch-resume` |
| `lock_commands.py` | `migration-lock` |
| `search_commands.py` | `search` |
| `skills_commands.py` | `skills sync`, `init-project` |
| `daemon_commands.py` | `daemon start`, `daemon stop`, `daemon status` |

Shared helpers: `orch/cli/utils.py` (session access, output formatting).

## Technology Stack

| Layer | Choice |
|-------|--------|
| ORM | SQLAlchemy 2.0 sync — `Mapped[]` declarative style |
| Driver | psycopg v3 (`psycopg[binary]`) — **NOT** psycopg2 |
| Migrations | Alembic 1.13+ |
| Config | python-dotenv — `load_dotenv()` called at module import |
| CLI | Click 8.1+ |
| Archive | zstandard (zstd) |

## Key Design Decisions

| Decision | Why |
|----------|-----|
| Sync SQLAlchemy (not async) | Daemon is single-threaded polling loop |
| PostgreSQL as sole source of truth | No markdown files, no race conditions |
| Composite PKs `(project_id, id)` | Multi-project isolation |
| Append-only `step_runs` / `fix_cycles` / `daemon_events` | Full audit trail |
| Two-tier archive (DB TEXT + zstd) | Always-viewable summaries + compact artifacts |
