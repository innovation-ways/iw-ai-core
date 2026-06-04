# orch/ — Core Python Package

IW AI Core's orchestration engine: ORM models, CLI, daemon, RAG, jobs, doc services, archive, and skills sync.

## Critical Rules

- **NEVER** execute docker container/volume/network management commands from orch code or scripts. Any shared-DB container management goes through `./ai-core.sh` or the operator. See `docs/IW_AI_Core_Agent_Constraints.md`.

## Package Structure

| Path | Purpose |
|------|---------|
| `config.py` | `load_config()` / `get_db_url()` — reads `.env`, fails fast on missing vars |
| `db/models.py` | All SQLAlchemy 2.0 ORM models + `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` constants |
| `db/session.py` | `engine`, `SessionLocal`, `get_session()` context manager |
| `db/identity.py` | DB instance-identity fingerprint (CR-00014) — `verify_instance_identity()`, `get_expected_instance_id()` |
| `db/migrations/` | Alembic versions — `env.py` imports `Base` from `orch.db.models`. Migration generation: use `make migration-pending MSG="…"` (not `alembic revision --autogenerate` directly). Sets `down_revision = "PENDING"`; resolved at merge time. See CR-00091. |
| `cli/` | Click command groups — agent-to-DB bridge |
| `daemon/` | Polling loop, worktree launch, fix cycles, merge queue, doc-job poller |
| `rag/` | Code Understanding: indexer, module-gen, symbol-gen, RAG Q&A. See `orch/rag/CLAUDE.md` |
| `jobs/aggregator.py` | Read-only unified view across CodeIndexJob / DocGenerationJob / Batch / research ProjectDoc |
| `doc_service.py` | CRUD for ProjectDoc, version snapshots, FTS querying |
| `doc_sections.py` | Pure markdown H2-section parsing (no DB) |
| `doc_diff.py` | Section-aware diffs between two markdown versions (no DB) |
| `test_runner.py` | Background subprocess engine for TestRun (tests + quality). Runs allure generate, parses results |
| `batch_planner.py` | Dependency analysis + execution plan + batch diagram generation |
| `archive/` | Two-tier archive (DB TEXT + zstd `.tar.zst`) |
| `skills/` | Skill sync engine — copies master skills to project worktrees |
| `utils/log_capture.py` | Step log capture utilities |

## Database Layer

**19 tables** (excluding in-progress OSS tables), all scoped by `project_id` for multi-project isolation.

**Orchestration core** (10): `projects`, `id_sequences`, `work_items`, `workflow_steps`, `step_runs`, `fix_cycles`, `batches`, `batch_items`, `migration_locks`, `daemon_events`.

**Observability** (1): `iw_core_instance` (single-row identity fingerprint, CR-00014).

**Frontend-triggered runs** (1): `test_runs` (append-only, `run_type='test'|'quality'`).

**Docs system** (7): `project_docs` (catalog + FTS), `project_doc_versions` (immutable snapshots), `doc_generation_jobs` (async AI regen queue), `doc_type_guides`, `doc_instance_guides`, `doc_section_guides` (editorial overrides).

**Code Understanding** (1): `code_index_jobs` (LanceDB indexing queue + progress).

**Composite PKs**: `work_items(project_id, id)`, batches, etc.

**Append-only** (never UPDATE): `step_runs`, `fix_cycles`, `daemon_events`, `test_runs`, `project_doc_versions`.

**FTS**: `work_items.design_doc_search` + `project_docs.content_search` (TSVECTOR) updated by triggers — raw DDL, not captured by `create_all()`. See `tests/CLAUDE.md`.

**Gotcha**: `DaemonEvent.metadata` → `event_metadata` in Python. SQLAlchemy reserves `metadata` on `DeclarativeBase` subclasses. DB column is still `metadata`.

## CLI Command Groups (`orch/cli/`)

Entry point: `iw` (defined in `pyproject.toml`). Composed from:

| Module | Commands |
|--------|----------|
| `id_commands.py` | `next-id`, `current-project` |
| `project_commands.py` | `register`, `projects list` |
| `item_commands.py` | `approve`, `unapprove`, `item-cancel`, `item-status`, `item-report`, `approve-merge`, `archive`, `register` |
| `step_commands.py` | `step-start`, `step-done`, `step-fail` |
| `batch_commands.py` | `batch-create`, `batch-approve`, `batch-status`, `batch-pause`, `batch-resume`, `batch-cancel` |
| `lock_commands.py` | `migration-lock` |
| `search_commands.py` | `search` |
| `skills_commands.py` | `skills sync`, `init-project` |
| `daemon_commands.py` | `daemon start`, `daemon stop`, `daemon status` |
| `db_commands.py` | `db-identity show`, `db-identity check` (exit 0/2/3 for bootstrap/mismatch/missing) |
| `doc_commands.py` | `doc-update`, `doc-job-start`, `doc-job-done`, `docs-check-stale`, `docs-export` |
| `worktree_commands.py` | `worktree-status` — git health of all active agent worktrees |

Shared helpers: `orch/cli/utils.py` (session access, output formatting).

## Daemon Modules (`orch/daemon/`)

| File | Purpose |
|------|---------|
| `main.py` · `__main__.py` | Entry point, poll loop |
| `state_machine.py` | Work item / step state transitions |
| `batch_manager.py` | Per-project batch orchestration (approved → executing → merge queue) |
| `batch_merge_hooks.py` | Post-merge hooks (e.g., doc regeneration triggers) |
| `merge_queue.py` | Serialised squash-merge queue |
| `migration_rebase.py` | Pre-merge rebase phase (CR-00021): fetch main, rebase branch, rewrite batch's stale migration down_revisions, commit the edit |
| `fix_cycle.py` | Fix-cycle lifecycle (up to 5 retries per step) |
| `step_monitor.py` | PID + heartbeat + stall detection |
| `doc_job_poller.py` | Polls `doc_generation_jobs`, launches AI agents (iw-doc-generator / iw-doc-system skills) |
| `execution_report.py` | Assembles execution reports from step logs (ANSI parsing, pass/fail classification) |
| `project_registry.py` | Loads `projects.toml` + per-project `.iw-orch.json`, syncs to DB on SIGHUP |
| `browser_env.py` | `browser_verification` step lifecycle (project-opted-in via `.iw-orch.json`) |
| `worktree_compose.py` | Per-worktree docker-compose stack lifecycle (project-opted-in via `ai-dev/iw-config/`). Renders Jinja2 template, discovers ports, runs seed script. |
| `worktree_reaper.py` | Label-based orphan/stale container reaper; runs on daemon startup and periodic schedule. |

## Technology Stack

| Layer | Choice |
|-------|--------|
| ORM | SQLAlchemy 2.0 sync — `Mapped[]` declarative style |
| Driver | psycopg v3 (`psycopg[binary]`) — **NOT** psycopg2 |
| Migrations | Alembic 1.13+ |
| Config | python-dotenv — `load_dotenv()` called at module import |
| CLI | Click 8.1+ |
| RAG | LanceDB + LlamaIndex CodeSplitter + Ollama embeddings (see `orch/rag/CLAUDE.md`) |
| Archive | zstandard (zstd) |

## Key Design Decisions

| Decision | Why |
|----------|-----|
| Sync SQLAlchemy (not async) | Daemon is a single-threaded polling loop |
| PostgreSQL as sole source of truth | No markdown files, no race conditions |
| Composite PKs `(project_id, id)` | Multi-project isolation |
| Append-only `step_runs` / `fix_cycles` / `daemon_events` / `test_runs` / `project_doc_versions` | Full audit trail |
| Two-tier archive (DB TEXT + zstd) | Always-viewable summaries + compact artifacts |
| DB-backed jobs (not in-memory queues) | Crash recovery; daemon + dashboard both observe the same state |
