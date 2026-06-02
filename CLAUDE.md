# IW AI Core — CLAUDE.md

AI orchestration platform that drives AI-assisted development across multiple projects: schedules LLM agents in git worktrees, aggregates background jobs, and surfaces a web UI for code understanding, docs, research, tests, and batch control.

## Quick Navigation

| Task | Location |
|------|----------|
| ORM models & schema | `orch/db/models.py` · `docs/IW_AI_Core_Database_Schema.md` |
| iw CLI commands | `orch/cli/` · see `orch/CLAUDE.md` |
| Daemon logic | `orch/daemon/` · `docs/IW_AI_Core_Daemon_Design.md` |
| Dashboard routes/templates | `dashboard/` · see `dashboard/CLAUDE.md` |
| Executor bash scripts | `executor/` · see `executor/CLAUDE.md` |
| Code Understanding (RAG) | `orch/rag/` · see `orch/rag/CLAUDE.md` |
| Doc generation & versioning | `orch/doc_service.py` · `orch/doc_sections.py` · `orch/doc_diff.py` |
| Test/Quality run engine | `orch/test_runner.py` · launched from `dashboard/routers/tests.py` & `quality.py` |
| Unified jobs view | `orch/jobs/aggregator.py` · `dashboard/routers/jobs_ui.py` |
| DB instance identity (CR-00014) | `orch/db/identity.py` · `dashboard/routers/healthz.py` |
| Worktree container isolation | `orch/daemon/worktree_compose.py` · `orch/daemon/worktree_reaper.py` · `docs/IW_AI_Core_Worktree_Isolation.md` |
| Test patterns & rules | `tests/conftest.py` · see `tests/CLAUDE.md` · `docs/IW_AI_Core_Testing_Strategy.md` · `skills/iw-ai-core-testing/SKILL.md` |
| Testing enhancement plan | `ai-dev/work/TESTS_ENHANCEMENT.md` · research `docs/research/R-00068-ai-core-test-quality-strategy.md` |
| Auto-merge resolution plan | `ai-dev/active/AUTO_MERGE_RESOLUTION.md` · research `docs/research/R-00076-llm-automated-merge-resolution.md` · tracking F-00084 |
| Configuration | `orch/config.py` (reads `.env`) · `projects.toml` |
| AI Assistant model allowlist | `projects.toml` `[projects.X.ai_assistant]` · `docs/IW_AI_Core_AI_Assistant_Models.md` |
| Evidences ingestion (CR-00025) | `orch/evidences.py` · hooks in `orch/cli/item_commands.py` (approve) and `orch/cli/step_commands.py` (step-done) |
| Migrations | `orch/db/migrations/versions/` |
| Pre-merge migration rebase (CR-00021) | `orch/daemon/migration_rebase.py` · `docs/IW_AI_Core_Daemon_Design.md` |
| Skills master copies | `skills/` (synced via `iw sync-skills`); design templates in `templates/design/` (synced via `iw sync-templates`) |
| Editorial guidelines (doc system) | `doc-system/` (brand, catalog, editorial) |

## Architecture

A single **daemon** polls PostgreSQL (port 5433) every 60s, picks approved batches across registered projects, creates git worktrees, launches LLM agents (opencode or claude-code), runs fix cycles, and squash-merges to main. The daemon also polls `DocGenerationJob` (AI doc regen) and `CodeIndexJob` (LanceDB indexing).

The **FastAPI dashboard** (port 9900) is the human interface. Per-project pages include:
- **Queue / History / Batches** — design and run work items
- **Code** — RAG-backed module browsing, symbol explainer, streaming Q&A with citations (`orch/rag/`)
- **Docs** — project doc catalogue with versioning, HTML/PDF exports, stale detection, and diffs; a global `/docs` route spans all projects
- **Research** — curated research documents (doc_type=research)
- **Tests / Quality** — launch and monitor test suites and quality gates from the UI (`orch/test_runner.py`)
- **Jobs** — unified table of background jobs (batches, code index, doc generation, research drafts)
- **Worktrees** — git status of all active agent worktrees

The **`iw` CLI** is the agent-to-DB bridge — agents call `iw step-done` to record results. All operational state lives in PostgreSQL — no files, no race conditions.

## Critical Rules

- **NEVER** connect tests to live DB (port 5433) — use testcontainers only (see `tests/CLAUDE.md`)
- **NEVER** call `importlib.reload(orch.config)` in tests — use `monkeypatch.delenv()` instead
- **NEVER** mock the database in integration tests — FOR UPDATE locking can't be tested otherwise
- **MUST** replace psycopg2 URLs in testcontainers: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in tests
- **CRITICAL**: `DaemonEvent.metadata` is named `event_metadata` in Python — SQLAlchemy reserves `metadata`
- **MUST** ensure `.env` and `.iw/` are listed in every managed project's `.gitignore` — daemon refuses to launch worktrees otherwise.
- **NEW**: per-worktree DB exists for app runtime when project has `ai-dev/iw-config/`. The agent's `IW_CORE_DB_*` env vars point at the per-worktree DB; `IW_CORE_ORCH_DB_*` always points at the global orch DB on 5433.
- **NEVER** apply an uncommitted Alembic migration to the production orch DB. Every worktree is `git worktree add`-ed from a commit, while its per-worktree DB is `pg_dump`-restored from prod — so a revision file that's in your working tree but not committed will be missing in worktrees while their DB is already at that revision, and `alembic upgrade head` dies with `Can't locate revision identified by '<rev>'`, taking down the worktree's E2E compose stack. Commit the revision file (or `alembic downgrade` and remove it) before doing anything else. (Diagnosed in I-00075 / I-00076.)
- **MUST** generate new Alembic migrations with `make migration-pending MSG="describe change"` rather than calling `alembic revision --autogenerate` directly. This writes `down_revision = "PENDING"` into the generated file; `migration_rebase.py` resolves it to the real chain head at merge time. See CR-00091.
- **MUST** update `_HEAD_REVISION` constants and catalog count constants in test files whenever a new migration is merged to main. Search for `_HEAD_REVISION` and for integer literals in test assertions that count runtime options or migration steps — these must reflect the new head after every merge. Failure to update them breaks every in-flight worktree simultaneously (CR-00095, Issue E).
- **MUST** keep Jinja2 `format`-filter calls `%`-style: `"%dm%02ds"|format(m, s)`, never `str.format`-style `"{}m{}s"|format(m, s)` (raises `TypeError: not all arguments converted during string formatting` at render time — and only when real data exercises the branch). Enforced by `make lint` → `scripts/check_templates.py`. (See I-00075.)
- **NEVER** use `agent-browser` for browser automation — use `playwright-cli` exclusively
- **NEVER** run `npx playwright install` or modify `.playwright/cli.config.json`
- **NEVER** run `docker compose up` (with or without `-d db`) against the orchestration DB from any directory — the default compose file is empty and the bootstrap file requires an explicit `-f` flag. Use `./ai-core.sh db start` instead. See `docs/IW_AI_Core_DB_Setup.md`.
- **NEVER** read, write, move, or delete anything under the backup directory (`IW_CORE_BACKUP_DIR`, default `/opt/postgres/data/backups`). Backup sets contain a `globals.sql` file with **role password hashes** (written `0600` inside a `0700` set directory); agents MUST NOT touch backup sets, copy them, or paste their contents into logs/reports/issues. Backups are created and pruned only by the daemon poller and the `iw db-backup` CLI. See `docs/IW_AI_Core_DB_Backup_Restore.md`.
- **MUST** append plain CSS rules directly to `dashboard/static/styles.css` when `make css` reports "Nothing to be done" or the Tailwind CLI fails (e.g., missing `postcss-selector-parser`) — plain CSS is served as-is, so no Tailwind recompile is required. Temporary mitigation until the Tailwind toolchain is repaired in worktrees (see I-00067).
- **MUST** invoke the `/iw-research` skill whenever the user asks for "a research", "online research", "deep research", "investigate X", "research X", or any equivalent phrasing — even when the agent believes it could answer inline. The user's expectation is that a research artifact is **filed in the IW AI Core database** so they can review it on the dashboard. **NEVER** silently perform inline web research as a substitute for `/iw-research`. The only acceptable exception is `/iw-research-quick`, and it may only be used when the user **explicitly** writes "quick research" / `/iw-research-quick` or asks a single trivial fact lookup that they have explicitly said should not be filed. When in doubt, default to `/iw-research`.

## Research Requests

Two skills exist; pick correctly:

| User phrasing | Skill |
|---------------|-------|
| "do a research", "research X", "deep research", "investigate", "evaluate options", "/iw-research" | `/iw-research` (files a Research doc, allocates `R-NNNNN`, registers in DB) |
| "quick research", "/iw-research-quick", a single explicit one-liner the user said should NOT be filed | `/iw-research-quick` (inline answer, no file, no ID) |

The default for this project is `/iw-research`. Do not downgrade to `/iw-research-quick` because the topic seems small — only the user can authorize that downgrade by using "quick" or `/iw-research-quick` explicitly.

## Configuration

All config in `.env` (gitignored). **NEVER** hardcode ports, URLs, or credentials.
Key vars: `IW_CORE_DB_HOST`, `IW_CORE_DB_PORT` (5433), `IW_CORE_DB_NAME`, `IW_CORE_DB_USER`, `IW_CORE_DB_PASSWORD`, `IW_CORE_DASHBOARD_PORT` (9900), `IW_CORE_POLL_INTERVAL`, `IW_CORE_STALL_THRESHOLD`, `IW_CORE_EXPECTED_INSTANCE_ID` (DB identity pin — see `orch/db/identity.py`).

**Database backups (F-00092)** — the daemon takes daily logical backups and operators can take on-demand ones via `iw db-backup` / `./ai-core.sh db backup`. Config vars:
- `IW_CORE_BACKUP_ENABLED` (default `true`) — disables the *scheduled* backup poller when false; `iw db-backup create` still works as a manual override.
- `IW_CORE_BACKUP_DIR` (default `/opt/postgres/data/backups`) — where backup sets are written.
- `IW_CORE_BACKUP_RETENTION_DAYS` (default `30`) — scheduled backups strictly older than this are pruned; manual/labeled backups are never pruned.
- `IW_CORE_BACKUP_TIME` (default `03:00`) — daily scheduled-backup time (HH:MM); the poller does missed-window catch-up after daemon downtime.

> ⚠️ **Same-disk limitation.** The default `IW_CORE_BACKUP_DIR=/opt/postgres/data/backups` is a *sibling* of `pgdata/` on the **same disk** as the data. It guards against the actual recurring failures — operator mistakes, bad migrations, and container displacement (the 2026-04-22 / 2026-05-29 / 2026-05-31 displacement incidents; `/opt/postgres/data` is a host bind mount, so `docker volume rm` / `compose down -v` cannot touch it) — but it does **NOT** protect against disk failure or `rm -rf /opt/postgres/data`. The path is configurable precisely so it can be repointed off-host (Tier-2 / I-00122 context). See [`docs/IW_AI_Core_DB_Backup_Restore.md`](docs/IW_AI_Core_DB_Backup_Restore.md).

Managed projects live in `projects.toml`; the daemon's `project_registry.py` syncs it to the DB on SIGHUP (`./ai-core.sh daemon reload`).

## Live DB Setup

**Port 5433** — pre-existing `postgres` Docker container (NOT docker-compose managed in production).

The default `docker-compose.yml` at the project root is **intentionally empty**. The `db` service lives in `docker-compose.bootstrap.yml` and is invoked only with `-f docker-compose.bootstrap.yml up -d db` — never implicitly. This prevents `docker compose up` from a worktree creating a rogue empty volume that clobbers the production DB (the 2026-04-22 data-loss incident).

See [`docs/IW_AI_Core_DB_Setup.md`](docs/IW_AI_Core_DB_Setup.md) for both setup paths.

**Never run `docker compose up` or `docker compose up -d db` in any form against the orchestration DB.** Always go through `./ai-core.sh db start`.

## Common Commands

```bash
./ai-core.sh install                                # uv sync + db start + migrate
./ai-core.sh start                                  # db → migrate → daemon → dashboard
./ai-core.sh status                                 # full status summary (inc. DB identity)
uv run iw --help                                    # CLI help
uv run iw db-identity check                         # verify DB instance fingerprint
make test-unit                                      # Fast tests (no containers)
make test-integration                               # Tests with PostgreSQL testcontainer
make lint                                           # ruff + node --check (dashboard JS) + scripts/check_templates.py (Jinja2)
make quality                                        # lint + format-check + mypy
make check                                          # quality + all tests
make db-migrate                                     # alembic upgrade head
uv run alembic revision --autogenerate -m "MSG"     # Generate migration
```

## Playwright CLI (Browser Automation)

Headless WSL/Linux — use `playwright-cli` exclusively. Binary: `~/.local/bin/playwright-cli`. Config: `.playwright/cli.config.json`.

**ALWAYS** run `playwright-cli kill-all` before starting a new browser session.
**NEVER** call `chromium.launch()` directly, use `agent-browser`, or run install commands.

```bash
playwright-cli kill-all              # Kill all sessions first
playwright-cli open <url>            # Open URL in browser
playwright-cli snapshot              # Accessibility snapshot of current page
playwright-cli screenshot            # Saves to .playwright-cli/page-<ts>.png (no path arg!)
                                     #   cp .playwright-cli/page-*.png <target>  ← to name the file
                                     #   playwright-cli screenshot <path> is INVALID — treats path
                                     #   as a page element ref, not a file destination
playwright-cli click <selector>      # Click an element
playwright-cli fill <selector> <v>   # Fill a form field
playwright-cli -s=<name> open <url>  # Named session (for auth persistence)
```

## Top-Level Layout

| Path | Purpose |
|------|---------|
| `orch/` | Python package: models, CLI, daemon, RAG, jobs, doc services |
| `dashboard/` | FastAPI web UI (routers, Jinja2 templates, htmx fragments) |
| `executor/` | Bash scripts invoked by the daemon (worktree setup/commit, step launch) |
| `tests/` | pytest suite — `unit/`, `integration/`, `dashboard/` |
| `skills/` | Master copies of agent skills — sync with `iw sync-skills` |
| `templates/design/` | Master copies of design doc templates — sync with `iw sync-templates` |
| `commands/` · `agents/` | Agent command specs (claude, opencode) — sync with `iw sync-agents` |
| `doc-system/` | Editorial config (brand, catalog, guidelines) used by doc-generator skills |
| `ai-dev/templates/` | Per-project copy of design doc templates (written by `iw sync-templates`) |
| `docs/` | Architecture, schema, CLI spec, daemon design, implementation plan |

## Docs Reference

| Document | What It Contains |
|----------|-----------------|
| `docs/IW_AI_Core_Database_Schema.md` | DDL, ENUMs, state machines, trigger code |
| `docs/IW_AI_Core_DB_Setup.md` | DB setup (production vs. bootstrap) and 2026-04-22 incident |
| `docs/IW_AI_Core_Tech_Stack.md` | Technology choices, test fixtures, Makefile |
| `docs/IW_AI_Core_Architecture.md` | System layout, end-to-end flow |
| `docs/IW_AI_Core_CLI_Spec.md` | Every `iw` command: inputs, outputs, DB ops |
| `docs/IW_AI_Core_Daemon_Design.md` | Daemon loop, state transitions, monitoring |
| `docs/IW_AI_Core_Agent_Constraints.md` | Docker/migration off-limits rules (R1, R2) |
| `docs/IW_AI_Core_Dashboard_Design.md` | Dashboard pages, htmx patterns, SSE |
| `docs/IW_AI_Core_Testing_Strategy.md` | Test layers, infrastructure, conventions, quality gates, known gaps, roadmap |
| `docs/implementation/00_INDEX.md` | Implementation plan index |
