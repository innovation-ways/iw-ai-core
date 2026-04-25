# R-00064 — Per-Worktree Database Isolation for Parallel AI-Agent Development

**ID**: R-00064
**Date**: 2026-04-25
**Mode**: deep
**Editorial Category**: functional
**Status**: draft

**Primary Question**: What isolation pattern should iw-ai-core adopt to give each parallel work-item worktree its own Postgres for app data, while keeping orch metadata global on 5433 and coexisting with CR-00021's merge-time rebase?

---

## Executive Summary

Across the AI-agent platforms surveyed (Devin, Codex, Cursor, Replit, Copilot Workspace), the universal pattern is **runtime isolation per parallel agent** — each task runs in its own VM, container, or filesystem snapshot, with the database forked or scoped alongside the code. iw-ai-core today only has **code isolation** (git worktrees) but shares the runtime DB on port 5433, which is the gap the user identified and the same gap that the OSS community has been filling for the last 12 months with tools like [worktree-compose](https://www.worktree-compose.com/) and [Coasts](https://www.penligent.ai/hackinglabs/git-worktrees-need-runtime-isolation-for-parallel-ai-agent-development/).

Three patterns dominate the landscape: **(1) docker-compose-per-worktree** with project-name isolation and dynamic ports — the user's preferred direction, validated as production-ready by multiple OSS tools and by Heroku Review Apps ([Heroku Dev Center](https://devcenter.heroku.com/articles/github-integration-review-apps)); **(2) Postgres template-database cloning** (`CREATE DATABASE … TEMPLATE …`), the Postgres-native approach used by IntegreSQL ([allaboutapps/integresql](https://github.com/allaboutapps/integresql)) and pgtestdb ([peterldowns/pgtestdb](https://github.com/peterldowns/pgtestdb)) with ~10–270ms clone times and now ~200ms even for 100GB DBs in Postgres 18 ([boringSQL](https://boringsql.com/posts/instant-database-clones/)); **(3) hosted DB branching** (Neon, Supabase, PlanetScale), correctly described as the gold standard for fully-isolated CoW preview environments but ruled out by the "no new dependencies" constraint.

The recommended path for iw-ai-core is a thin **per-worktree docker-compose stack** that runs one ephemeral Postgres container alongside the worktree, isolates it via `COMPOSE_PROJECT_NAME` and a deterministic port (5433 + worktree-slot), and seeds it from a single master migration apply — while the iw CLI inside the worktree continues to write orch metadata to the global 5433 instance via a separate connection. **Crucially, this is orthogonal to CR-00021** — Alembic chain history lives in `.py` files in git, not in DB state, so two parallel branches still produce two `down_revision` strings pointing at the same parent and still need merge-time rebasing. The DB isolation prevents *runtime* schema interference (Backend step in worktree A can't see Tests step in worktree B's `ALTER TABLE`), not *file-level* chain conflicts.

---

## Findings

### Finding 1 — Every serious AI-agent platform isolates runtime per parallel agent; iw-ai-core is the outlier [HIGH]

The market has converged on **VM-per-task or container-per-task** for parallel AI agents, not just worktree-per-task:

- **Devin (Cognition)**: "Each managed Devin is a full Devin, running in its own isolated virtual machine with its own terminal, browser, and development environment, with each one able to independently run shell commands, execute tests, and verify its own changes" ([Cognition blog](https://cognition.ai/blog/devin-can-now-manage-devins); [Medium deep-dive](https://medium.com/@takafumi.endo/agent-native-development-a-deep-dive-into-devin-2-0s-technical-design-3451587d23c0)).
- **OpenAI Codex (cloud)**: "Codex cloud runs in isolated OpenAI-managed containers, preventing access to your host system or unrelated data … Codex creates a container and checks out your repo at the selected branch or commit SHA" ([OpenAI Codex docs](https://developers.openai.com/codex/cloud/environments)).
- **Cursor Background Agents**: "Background agents are asynchronous remote agents that run in isolated Ubuntu cloud VMs" and the foreground agent uses Apple Seatbelt / Linux Landlock+seccomp for filesystem and network sandboxing ([Cursor blog](https://cursor.com/blog/agent-sandboxing); [InfoQ on Cursor 3](https://www.infoq.com/news/2026/04/cursor-3-agent-first-interface/)). Cursor caps parallelism at 8 concurrent agents per prompt, "uses git worktrees or remote machines to prevent file conflicts, with each agent operating in its own isolated copy of your codebase" ([Morph guide](https://www.morphllm.com/cursor-background-agents)).
- **GitHub Copilot Coding Agent**: "While working on a task, Copilot has access to its own ephemeral development environment, powered by GitHub Actions … Each task uses an ephemeral workspace—no state leakage between tasks" ([GitHub docs](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/customize-the-agent-environment)).
- **Replit Agent 4**: snapshots include filesystem, Postgres, and compute env at the block level, with **prod/dev DB split per project**: "we use separate production and development databases and grant the Agent access only to the development database" ([Replit Snapshot Engine blog](https://blog.replit.com/inside-replits-snapshot-engine); [Replit Agent 4 announcement](https://blog.replit.com/introducing-agent-4-built-for-creativity)).
- **Aider / Claude Code / Sweep style** (the closest analog to iw-ai-core today): "git worktrees became an agent primitive" but stop at code isolation. The community has now explicitly named this gap: *"Two branches can each have their own file tree and still both try to write migrations into the same shared database … a test can fail because the branch is wrong, because the port was already taken, because a stale database volume leaked in"* ([Penligent on git worktree runtime isolation](https://www.penligent.ai/hackinglabs/git-worktrees-need-runtime-isolation-for-parallel-ai-agent-development/)).

**Implication for iw-ai-core**: the user's proposal aligns with where the entire AI-coding-agent market has settled. The remaining choice is *how* to achieve runtime isolation, not *whether*.

### Finding 2 — Pattern catalog: how each option isolates, costs, and interacts with CR-00021 [HIGH]

#### 2a. Docker-compose per worktree (one ephemeral Postgres container per item) — **strong recommended**

How: each `iw-core/worktrees/<item>/` gets its own `docker-compose.worktree.yml` (or a generated override of the bootstrap one), launched with a unique `COMPOSE_PROJECT_NAME=iwcore-<item>` and a unique host port. Containers, volumes, and networks are namespaced by project name; cleanup is `docker compose down -v` on archive.

- **Isolates**: data + schema + extensions + ports. Full physical separation.
- **Boot time**: 2–8 seconds for an alpine Postgres image with `tmpfs` data directory; longer if you mount fixtures.
- **Resource cost**: postgres alpine RSS ~25–60 MB idle per container. On a 32GB workstation, 50+ concurrent worktrees is feasible from a memory standpoint; CPU is bursty so concurrent migrations are the practical ceiling.
- **Cleanup**: `docker compose --project-name iwcore-<item> down -v` removes containers, networks, and named volumes deterministically. Stragglers can be reaped by labelling and a periodic `docker container prune --filter label=iwcore.role=worktree-db`.
- **Existing OSS prior art**:
  - [worktree-compose](https://www.worktree-compose.com/): "Unique COMPOSE_PROJECT_NAME per worktree. Own containers, networks, and volumes." Allocates ports via `20000 + default_port + worktree_index` — e.g. postgres on main 5434, worktree 1 gets 25435, worktree 2 gets 25436. `wtc clean` does the cleanup; `.env` overrides are "idempotently injected." Built-in MCP server for AI agents.
  - [dockportless](https://github.com/mazrean/dockportless): "designed for developing multiple features in parallel using git worktrees, where each worktree gets its own project name, ports, and proxy routes — no collisions, no coordination needed."
  - **Coasts** (described in the Penligent piece above): introduces per-service "assign policies" — `none | hot | restart | rebuild` — letting the operator declare which services are isolated per worktree vs. shared.
- **CR-00021 interaction**: ORTHOGONAL. CR-00021 fixes file-level chain conflicts; this fixes runtime schema interference. The pre-merge dry-run in CR-00021 still spins a fresh testcontainer to apply the worktree's `versions/` chain — which is what makes its rebase phase trustworthy. Per-worktree DB does *not* replace the dry-run because the dry-run validates the post-rebase chain against a clean baseline, while the per-worktree DB carries whatever schema state the agent built up across multiple steps.

#### 2b. Postgres template-database cloning (one shared PG instance, `CREATE DATABASE … TEMPLATE base`) — **second choice**

How: keep one Postgres instance (the existing 5433), promote a "baseline" DB to template, and on worktree creation run `CREATE DATABASE iwcore_<item> TEMPLATE iwcore_baseline;`. Each worktree gets its own *logical database* on the shared instance. iw-ai-core's app code points at `iwcore_<item>`, the iw CLI at `iw_orch`.

- **Isolates**: data + schema. Same instance shares config, extensions, shared_buffers. Each DB is a separate file tree under `base/`.
- **Boot time**: native `STRATEGY=WAL_LOG` (default since PG15) takes 67s for a 6GB DB; **PG18's new `file_copy_method=clone` with `STRATEGY=FILE_COPY` brings that to 212ms** — a 315x speedup using filesystem reflinks ([boringSQL](https://boringsql.com/posts/instant-database-clones/); [Neon Branching](https://neon.com/storage)). Filesystem requirements: XFS, ZFS, APFS, or btrfs — **ext4 is not listed as compatible**; macOS APFS works.
- **Resource cost**: shared shared_buffers/WAL. Disk-only divergence. Hugely cheaper per-worktree than separate containers.
- **Cleanup**: `DROP DATABASE iwcore_<item>` on archive. No container/volume housekeeping.
- **Hard PG mechanics constraint**: "no other sessions can be connected to the source database while it is being copied. CREATE DATABASE will fail if any other connection exists when it starts; during the copy operation, new connections to the source database are prevented" ([Postgres 18 Template Databases docs](https://www.postgresql.org/docs/current/manage-ag-templatedbs.html)). Translation for our case: the "baseline" template DB must be **idle** — nothing connects to it, the daemon doesn't share it. We'd maintain it as `datistemplate=true, datallowconn=false` and only flip `allowconn=true` briefly when refreshing it after a main-branch merge.
- **OSS validation**: IntegreSQL ([allaboutapps/integresql](https://github.com/allaboutapps/integresql)) serves test DBs to parallel runners with ~11–26ms clone time on average via this exact pattern. pgtestdb ([peterldowns/pgtestdb](https://github.com/peterldowns/pgtestdb)) does the same as a Go library: "Creating a new database from a template is very fast, on the order of 10s of milliseconds". The model is proven — the question for iw-ai-core is whether to repurpose it for hours-long dev environments rather than millisecond-long test invocations.
- **CR-00021 interaction**: same as 2a — orthogonal.
- **Drawback vs. compose-per-worktree**: shared Postgres process means an OOM in one worktree's queries can affect everyone. Also, the daemon already runs the live orch DB on 5433; co-tenanting per-worktree DBs on the same instance increases blast radius for the production orch DB (the one the 2026-04-22 incident protected).

#### 2c. Postgres schemas with `search_path` per worktree — **rejected**

How: one DB, one schema per worktree, `SET search_path = iwcore_<item>, public;` per connection.

- **Isolates**: schema only. Connections, locks, and shared resources are common.
- **Postgres-specific gotchas that disqualify this**: "Anything other than session mode in PgBouncer won't let you use search_path to switch tenants, and if you try to use search_path in transaction mode, you can even unknowingly mix tenant's data" ([Arkency](https://blog.arkency.com/what-surprised-us-in-postgres-schema-multitenancy/)). "PostgreSQL extensions need to be installed in one specific schema that is available in the search_path" — meaning every per-worktree schema would need `pg_trgm`/FTS extensions re-pointed.
- **Migration interaction**: Alembic by default targets one schema. Multi-schema migration would require either per-schema Alembic configs (complex and parallel-unsafe) or schema-aware migration runners — a significant complication on top of CR-00021.
- **Verdict**: rules out for our case. Compose-per-worktree is simpler and stronger.

#### 2d. DB branching services — Neon, Supabase, PlanetScale — **rejected by user constraint**

How: cloud-hosted Postgres (or Vitess/MySQL for PlanetScale) where "branch" is a CoW pointer at the storage layer. Branch creation is O(1) regardless of DB size.

- **Neon**: "A branch is a copy-on-write clone of your data. When you create a branch, no data is copied. The branch is a metadata pointer to a specific point in the parent database's write-ahead log history. Pages are only written to the branch's storage when they are modified. This means branching is an O(1) operation regardless of database size, completing in under a second" ([Neon Branching docs](https://neon.com/docs/introduction/branching)). Branches scale to zero. Pricing: "$0.35 per GB-month" with child branches paying only for divergent writes. Neon explicitly markets to AI agents — 80% of new Neon DBs in 2026 are created by agents ([Neon AI Agents page](https://neon.com/use-cases/ai-agents)).
- **Supabase Branching**: "When you create a branch in Supabase, you get a fully functional, isolated Postgres instance with its own URL, credentials, and dashboard view" ([Supabase Branching docs](https://supabase.com/docs/guides/deployment/branching)).
- **PlanetScale**: branch + deploy-request workflow with native three-way merge of schema diffs ([PlanetScale three-way merge](https://planetscale.com/blog/database-branching-three-way-merge-schema-changes)). PlanetScale's "safe migrations" enforces non-blocking DDL via gh-ost-style tooling. **Note**: the three-way merge here is roughly the equivalent of CR-00021's rebase phase but operating on schema state instead of migration files.
- **Why ruled out**: introduces a hard dependency on a hosted SaaS DB for what is a local dev workflow. Conflicts directly with the user's stated constraint ("avoid adding new tech dependencies"). Also conflicts with iw-ai-core's offline-friendly local-first posture.
- **CR-00021 interaction**: PlanetScale would supplant CR-00021 entirely (their three-way merge owns the linearization). Neon/Supabase don't — you'd still need merge-time chain reconciliation. So we lose CR-00021's surface area only with PlanetScale, and we don't run MySQL.
- **Reference value**: keep these as a "what we'd do if the constraint changed" footnote; the model is the right destination if iw-ai-core ever moves to hosted infra.

#### 2e. Container-per-PR / preview environments (Heroku Review Apps, Vercel + Neon, Render) — **architectural inspiration, not directly applicable** [HIGH]

How: every PR gets a full ephemeral environment (app + DB + URL) lifecycled by webhook on PR open/close. "Review apps are instant, disposable Heroku app environments that can spin up automatically with each GitHub pull request" ([Heroku Dev Center](https://devcenter.heroku.com/articles/github-integration-review-apps)). Vercel pairs with Neon for the DB half: "the integration receives a webhook from Vercel and creates a new Neon branch named preview/<git-branch> using the Neon API. Vercel receives the new connection string and injects it as environment variables for that specific deployment only" ([Neon × Vercel docs](https://neon.com/docs/guides/vercel-managed-vercel-integration-previews)).

- **Transferable lesson**: the *trigger* is the same (worktree creation ≈ PR open), the *teardown* is the same (worktree archive ≈ PR merge), the *secret-injection* pattern is the same (per-worktree connection string handed to the app via env). We can reuse this mental model, just on a single workstation instead of cloud.
- **Not directly applicable**: full preview-env stacks include CDN, ingress, build pipeline. We need only the DB slice.

#### 2f. pg_tmp / testcontainers / IntegreSQL "as dev env" — **unify with tests, not replace** [MEDIUM]

How: reuse the same ephemeral-PG tooling that already powers integration tests, but keep the container alive for the duration of the worktree.

- **Testcontainers Desktop**: explicitly markets reusable containers for dev. "When you spin up a container with reuse, a hash is calculated based on the container's configuration. When you request another container with the same configuration which yields the same hash value, then the existing container will be reused" ([Testcontainers reuse docs](https://java.testcontainers.org/features/reuse/); [Testcontainers Desktop guide](https://testcontainers.com/guides/simple-local-development-with-testcontainers-desktop/)). **Critical constraint**: "Reusable containers are not suited for CI usage" — only for desktop/dev.
- **pg_tmp**: "reduces the wait time for a new database to less than one second by initializing a database in the background that is used by subsequent invocations" ([eradman.com/ephemeralpg](https://eradman.com/ephemeralpg/)). Optimised for sub-second test setup, not multi-hour dev sessions.
- **Recommendation**: do *not* try to make tests share the per-worktree dev DB. Keep `make test-integration` on testcontainers (current behavior, mandated by `tests/CLAUDE.md`). The per-worktree dev DB is a *separate* concern that serves the Backend step's runtime needs and any agent-driven manual smoke checks.

### Finding 3 — Tools that already implement compose-per-worktree are production-ready [HIGH]

Two OSS tools solve the user's exact request and give us either a drop-in or a strong reference implementation:

| Tool | Language | Mechanism | License | AI-agent integration |
|------|----------|-----------|---------|----------------------|
| [worktree-compose](https://www.worktree-compose.com/) | Node CLI | `COMPOSE_PROJECT_NAME` + port-formula injection + `.env` overrides | (check repo) | Built-in MCP server |
| Coasts (referenced via [Penligent](https://www.penligent.ai/hackinglabs/git-worktrees-need-runtime-isolation-for-parallel-ai-agent-development/)) | Go (apparent) | `Coastfile` toml with per-service `assign` policies (`none|hot|restart|rebuild`) | (check repo) | Designed for AI agents, ships Coastguard observability UI |
| [dockportless](https://github.com/mazrean/dockportless) | Go | Local service router with auto port assignment, like `vercel/portless` for compose | MIT | Generic |

**For iw-ai-core**: rather than adopting one of these wholesale, the closer analog is to inline the pattern into `executor/worktree_setup.sh` because (a) iw-ai-core already has a specialized worktree lifecycle owned by the daemon, not by humans typing `wtc`, (b) the per-worktree DB needs to interleave with `iw step-done` calls hitting the *global* 5433 — that two-DB topology is unique enough that a generic tool will need configuration anyway, and (c) we want the dev DB lifecycle bound to the daemon's `BatchItem` state machine, not to a separate CLI's state.

### Finding 4 — CR-00021 stays orthogonal: per-worktree DB is necessary but not sufficient [HIGH]

This is the most important finding for sequencing.

CR-00021 solves a **file-level conflict**: two parallel branches each `alembic revision --autogenerate -m "..."` produce two `.py` files with the same `down_revision = "rev1"`. At merge time the chain has multiple heads. The fix is text rewriting at merge time. **The DB has nothing to do with this** — Alembic chain history is files in git, and a per-worktree DB does not change what files those branches produce.

Per-worktree DB solves a **runtime interference problem**: today, when the Database step in worktree A runs `alembic upgrade head` against 5433 (which agents are forbidden from doing — `safe_migrate.AgentContextForbiddenError`) or even when a fix-cycle agent runs an integration test that writes through SQLAlchemy and forgets to roll back, the live state on 5433 changes. Worktree B's Backend step then sees that change, possibly silently relies on it, and ships code that breaks the next time main is "clean." This is precisely the class of bug the agent-context guard tries to prevent — but the guard is a defense-in-depth tripwire, not isolation. Per-worktree DB is the actual isolation.

Therefore:
- Per-worktree DB does **not** replace CR-00021's pre-merge rebase or pre-merge dry-run. The dry-run still needs to spin a *fresh* PG and apply the post-rebase chain to validate it.
- CR-00021 does **not** replace per-worktree DB. The chain rewrite happens once per batch at merge time; it does not isolate the dozens of step-time DB reads/writes that happen *during* the batch.
- Both should ship.

A pleasant secondary benefit: with per-worktree DB, the `safe_migrate.AgentContextForbiddenError` rule could in principle be relaxed *for the per-worktree DB only* (the agent can run `alembic upgrade head` against its own private PG with no blast radius), while still enforced for the global 5433. This is a follow-on simplification, not a goal of this CR.

### Finding 5 — `make test-integration` should remain on testcontainers; per-worktree DB is for the Backend step's runtime [HIGH]

Tests must stay reproducible from a clean baseline; that's why `tests/CLAUDE.md` mandates testcontainers. Reusing the per-worktree dev DB for tests would break that contract: the dev DB will accumulate state (Backend step seeded data, the agent's manual experiments, half-applied migrations during a fix cycle). Tests that pass against the dev DB might not pass against a fresh DB on CI.

Concrete rule: **the per-worktree DB is the connection that `IW_CORE_DB_URL` (in the worktree's `.env`) points to for app-runtime use; testcontainers continue to be spun up by `tests/integration/conftest.py:1-11` for tests; the global 5433 is what `iw step-done` writes to via a separate connection string.** Three connection strings, three concerns.

---

## Operational Concerns Table — top three patterns

Scoring scale: ✅ strong / ◐ acceptable / ⚠️ weakness / ❌ blocker

| Concern | Compose per-worktree (recommended) | Template DB on shared PG | Neon-style branching (out of scope) |
|---------|-----------------------------------|--------------------------|-------------------------------------|
| **Boot time** | ◐ 2–8s (alpine PG cold start, tmpfs data) | ✅ 10–270ms (PG ≤17), ~200ms even at 100GB (PG18 with reflink) | ✅ <1s, O(1) regardless of size |
| **Memory cost @ 8 worktrees** | ◐ ~200–500 MB total (8 × alpine PG idle) | ✅ ~50–100 MB (one shared shared_buffers) | n/a (offloaded) |
| **Disk cost** | ◐ N × DB size (no CoW unless you mount BTRFS/ZFS subvolumes) | ✅ shared until divergence | ✅ shared until divergence |
| **Implementation complexity** | ◐ ~150 LOC bash + a compose-template + a port allocator | ⚠️ ~300 LOC (template-refresh logic, idle-connection enforcement, PG18 reflink prerequisite, `datallowconn` toggling) | ❌ requires hosted infra adoption |
| **Port/conflict management** | Daemon allocates `5433 + slot_index` (slot tracked in `BatchItem` row) | ✅ N/A — same port, different DB names | ✅ N/A — different host per branch |
| **`.env` handling** | Worktree's `.env` overrides `IW_CORE_DB_PORT` and `IW_CORE_DB_NAME`; `.env.iw-core-orch` carries the global 5433 connection used by the iw CLI | Worktree's `.env` overrides only `IW_CORE_DB_NAME`; same orch host/port handles both | n/a |
| **Cleanup on archive** | ✅ `docker compose --project-name iwcore-<id> down -v` (label + scheduled prune as belt-and-suspenders) | ◐ `DROP DATABASE iwcore_<id>` — must terminate connections first (`pg_terminate_backend`) | ✅ webhook-driven |
| **Cleanup on daemon crash** | ◐ Stragglers possible — solved by labelling + `docker container prune --filter label=iwcore.role=worktree-db` on daemon startup, similar to Testcontainers' Ryuk pattern | ⚠️ Stragglers persist as DB rows; needs reconciliation against `BatchItem.status NOT IN merged|archived` | ✅ |
| **Data seeding (baseline schema)** | Seed by running `alembic upgrade head` against the new container at worktree creation. Bake-in option: pre-build a PG image with migrations applied, refresh on every main-branch merge. | Refresh `iwcore_baseline` template DB whenever main lands a new migration; `CREATE DATABASE … TEMPLATE iwcore_baseline` clones it for the worktree | n/a |
| **Blast radius of failure** | ✅ Per-worktree container — one OOM does not impact others or the live 5433 | ⚠️ Shared PG process — query-storm in one worktree hits everyone, including production orch | ✅ |
| **CR-00021 interaction** | Orthogonal. Both ship. | Orthogonal. Both ship. | Supplanted only by PlanetScale's three-way merge — not a Postgres branching service. |
| **Postgres version requirement** | Any | PG18 strongly preferred for `file_copy_method=clone`; PG15+ acceptable with WAL_LOG (slower clones) | Service-managed |
| **Filesystem requirement** | None | XFS/ZFS/APFS/btrfs for fast clone; ext4 OK with WAL_LOG | None |

**Recommendation: compose per-worktree.** Template DBs are a strong runner-up but introduce a meaningful coupling to PG18+reflink to be competitive on boot time, and the shared-process blast radius in the same instance that hosts the production orch DB is a real concern given the 2026-04-22 incident's lesson. Compose-per-worktree pays a one-time per-worktree boot cost (seconds, not minutes), trades it for **physical isolation that cleanly mirrors the worktree boundary**, and keeps the production 5433 untouched.

---

## Recommendation for iw-ai-core

### Approach
Add a per-worktree Postgres container, lifecycled by the daemon, named and ported deterministically from the `BatchItem.id`. The worktree's `.env` is rewritten to point app-runtime DB connections at the new container; orch-metadata access is moved to a separate, explicit env variable that always points at the global 5433.

### Concrete `.env` layering

Today, `executor/worktree_setup.sh:116-142` copies the main `.env` into the worktree, so `IW_CORE_DB_*` reaches both the app code and `iw step-done`. Split that:

```
# Inherited from main .env (orch metadata, never overridden by worktree)
IW_CORE_ORCH_DB_HOST=localhost
IW_CORE_ORCH_DB_PORT=5433
IW_CORE_ORCH_DB_NAME=iw_orch
IW_CORE_ORCH_DB_USER=iw_orch
IW_CORE_ORCH_DB_PASSWORD=...

# Set by worktree_setup.sh — points at the per-worktree container
IW_CORE_DB_HOST=localhost
IW_CORE_DB_PORT=15433       # 5433 + (slot_index * 100), slot in [1..N]
IW_CORE_DB_NAME=iw_orch     # same name; different physical PG
IW_CORE_DB_USER=iw_orch
IW_CORE_DB_PASSWORD=...
IW_CORE_WORKTREE_SLOT=1
COMPOSE_PROJECT_NAME=iwcore-<batch_item_id>
```

`orch/db/session.py` keeps using `IW_CORE_DB_*` for app sessions. The iw CLI is changed to read `IW_CORE_ORCH_DB_*` for the bridge connection (this is a focused 1-step diff in `orch/cli/__init__.py` or wherever the engine is built — does not affect agents).

### `executor/worktree_setup.sh` changes

After the existing worktree creation and `.env` expansion, add a step that:

1. Acquires a slot index from the daemon (RPC: `GET /internal/worktree-slot?batch_item_id=…` returns 1–32). Slot is stored on `BatchItem.worktree_slot` so it survives daemon restart.
2. Computes `WT_DB_PORT = 5433 + slot_index * 100`. Hard cap at 32 concurrent worktrees (matches current daemon's parallelism ceiling).
3. Renders a `docker-compose.worktree.yml` from a template, substituting `${COMPOSE_PROJECT_NAME}` and `${WT_DB_PORT}`. The compose file declares one `postgres:16-alpine` service with `tmpfs:/var/lib/postgresql/data` (in-memory data for speed; persist to a named volume only if the agent's session needs to survive a host reboot, which it shouldn't).
4. `docker compose --project-name iwcore-<id> --file docker-compose.worktree.yml up -d`.
5. Waits for `pg_isready` (timeout 30s).
6. Runs `alembic upgrade head` against the new container to seed the schema. (The agent context guard is bypassed for the per-worktree DB only — see Risks/Open Question 4 below.)
7. Writes the per-worktree `.env` with the resolved port.

### Cleanup hook

`executor/worktree_commit.sh` (success path) and the daemon's archive path both call `docker compose --project-name iwcore-<id> down -v`. Belt-and-suspenders: every Postgres container created by this flow gets `--label iwcore.role=worktree-db --label iwcore.batch_item=<id>`. On daemon startup, run `docker ps -a --filter label=iwcore.role=worktree-db` and reconcile against `BatchItem.status NOT IN ('merged','archived','restarted')` — anything orphaned gets `docker rm -fv`. Same idea as Testcontainers' Ryuk reaper, scoped to our label.

### Daemon port allocator

Add `BatchItem.worktree_slot INT NULL UNIQUE WHERE worktree_slot IS NOT NULL` (partial unique index). Slot allocation is a `SELECT … FOR UPDATE` against the existing in-flight set, picking the smallest unused integer in [1..32]. Released on archive. This is ~30 LOC in `orch/daemon/batch_manager.py` next to the existing worktree setup call.

### `make test-integration` interaction

Unchanged. Tests continue to use `tests/integration/conftest.py:1-11`'s testcontainers fixtures. The per-worktree DB is for app runtime, not tests.

### Milestones

**Week 1 (PoC):** Hand-roll the compose template and port-allocator math; manually verify two parallel worktrees can both run `make` targets without colliding. Wire `executor/worktree_setup.sh` end-to-end. Manually validate `iw step-done` still writes to global 5433.

**Week 2:** Daemon-side slot allocator + `BatchItem.worktree_slot` migration (CR-00021 must have shipped first). Cleanup hook on `worktree_commit.sh`. Belt-and-suspenders Ryuk-style reaper on daemon startup.

**Week 3:** Tests. Two integration tests: (a) two parallel worktrees each apply a different schema change, both succeed and don't see each other's tables; (b) crashing the daemon mid-batch leaves no leaked containers after the next start.

**Week 4 (stretch):** Relax `safe_migrate.AgentContextForbiddenError` to allow the agent to run `alembic upgrade head` against the per-worktree DB. This unlocks more realistic agent loops (the agent can iterate on a migration without daemon involvement). Keep the guard for the global 5433.

**Month 2 (stretch):** Evaluate whether to switch the per-worktree DB from "ephemeral container" to "template-clone on shared PG" once iw-ai-core upgrades to PG18 + a reflink-capable filesystem. The compose-per-worktree pattern would remain the API surface; only the implementation under `executor/worktree_setup.sh` would change. This is a bet on PG18's `file_copy_method=clone` becoming production-stable.

---

## Risks, Edge Cases, and Open Questions

1. **Two CLIs, one process: connection-pool confusion.** The worktree process holds two engines — one for app DB (per-worktree port), one for orch DB (5433). SQLAlchemy session contamination is a known footgun. Mitigation: encapsulate orch access in a dedicated `orch_session()` factory (5–10 LOC), audit `iw` CLI commands to ensure they import only that, and add a unit test that asserts the engine URL of the `iw step-done` code path equals `IW_CORE_ORCH_DB_URL`.

2. **Daemon-vs-worktree race on slot release.** If a worktree fails between steps and the daemon re-launches it, does the new attempt reuse the old slot or get a fresh one? Reuse is cheaper but requires that the leftover container is fully torn down first. Recommendation: always tear down + reallocate; idempotent and robust.

3. **Orch DB schema drift between CR ships.** CR-00021 adds `pending_migration_log.old_revision` and `migration_rebase_failed` enum value. This research's CR adds `BatchItem.worktree_slot`. Both are additive; both must run as separate Alembic migrations in dependency order. CR-00021 must precede this CR — already accepted. Note: the per-worktree-DB CR's own migration cannot, of course, run against per-worktree DBs; it runs against the global orch DB via the standard daemon-applies path.

4. **Should `safe_migrate.AgentContextForbiddenError` be relaxed for the per-worktree DB?** If yes, the agent's Database step can `alembic upgrade head` locally and validate the migration applies cleanly *during the step* — before merge time. This effectively turns the agent's worktree into an "early dry-run." Strong upside; the only downside is divergence from the "agents generate, daemon applies" rule that `docs/IW_AI_Core_Agent_Constraints.md` enshrines. Open for design discussion in the implementation CR.

5. **Postgres image cold start cost dominates if every step boots a fresh container.** Alpine PG cold start can be 5–10s. Across, say, 8 work items per day per developer, that's tolerable; across 50, it's not. Mitigations to evaluate: (a) keep the container alive for the full lifecycle of the worktree (its lifetime is hours, not seconds), (b) use `tmpfs` for data dir to skip disk I/O, (c) pre-bake a PG image with our schema applied so seeding is `docker run` rather than `alembic upgrade head`. Recommended: (a) + (b) at first; (c) if measurements show it matters.

6. **Filesystem cleanup on a host crash.** `docker compose down -v` requires the daemon to be alive. If the host hard-crashes mid-batch, we leak named volumes. Mitigation: use `tmpfs` (no volume) by default, and require the on-startup reaper to also `docker volume prune --filter label=iwcore.role=worktree-db` for the persistent-volume case.

7. **WSL specifics.** iw-ai-core runs on WSL. `tmpfs` and Docker Desktop play well together, but the WSL2 Docker integration sometimes leaves dangling containers when the WSL VM is restarted. The Ryuk-style reaper handles this, but worth a smoke test on the actual workstation early.

8. **Interaction with the `playwright-cli` browser-verification step.** The qv-browser step opens a browser pointing at the worktree's running app. If the app reads `IW_CORE_DB_*` and connects to the per-worktree DB, the browser sees worktree-isolated state — desirable. But the app must be told the app DB port via the same `.env` the agent uses. Requires a follow-up audit of `dashboard/` startup code to confirm it reads `IW_CORE_DB_PORT`, not a hard-coded 5433 (the dashboard's `orch/config.py` already sources from env, so this should be free).

9. **Compose vs. plain `docker run`.** Compose is preferred because (a) it's already how iw-ai-core boots `db` in `docker-compose.bootstrap.yml`, (b) it gives us volumes/networks/labels in one declarative file, (c) cleanup is one command. The risk to flag: the empty default `docker-compose.yml` documented in CLAUDE.md as a 2026-04-22 protection — a stray `docker compose up -d` from a worktree directory could re-trigger that incident. Solution: place the per-worktree compose in a *non-default* path (`worktrees/<id>/.iw/docker-compose.worktree.yml`) and never name it `docker-compose.yml`. Operators running `docker compose up` from the worktree root see the same empty file as before; only the daemon's `--file` flag picks up the worktree DB.

10. **Connection strings in logs.** `iw` CLI calls log connection strings on failure. Per-worktree connection strings on logs are fine in principle but accumulate noise. Mitigation: redact passwords in log formatters (already done for the orch DB; mirror the redaction).

---

## Limitations

- **No measurements yet.** Boot times and memory numbers above are from referenced sources or back-of-envelope; iw-ai-core-specific timings would need a one-day spike to validate. Particularly, the question of whether 8–16 concurrent compose-per-worktree stacks remain under 4 GB on the user's workstation needs measurement, not theory.
- **Coasts and worktree-compose are recent (2025–2026).** Both have GitHub repos but the production-deployment evidence base is thin. Treat them as reference designs, not battle-tested dependencies.
- **PG18's `file_copy_method=clone` is brand new (2026 release).** The 315x speedup is a single benchmark on a 6 GB DB. Filesystem dependency (XFS/ZFS/APFS/btrfs) is a real adoption blocker — most production Linux installs are ext4. This is why the recommendation defers template-DB cloning as a "Month 2 stretch" rather than a primary path.
- **Devin/Codex/Cursor architecture details rely on engineering blogs and product docs.** Internal implementation may differ; the convergence on "per-task isolated runtime" is the only safe high-confidence claim.
- **No prototype yet.** The recommendation is design-grade, not proven. Week-1 milestone explicitly is the PoC.

---

## Sources

| # | Title | Credibility | URL |
|---|-------|-------------|-----|
| 1 | PostgreSQL 18 — Template Databases (official docs) | Authoritative | https://www.postgresql.org/docs/current/manage-ag-templatedbs.html |
| 2 | PostgreSQL 18 — CREATE DATABASE (official docs) | Authoritative | https://www.postgresql.org/docs/current/sql-createdatabase.html |
| 3 | Instant database clones with PostgreSQL 18 (boringSQL) | High (technical blog) | https://boringsql.com/posts/instant-database-clones/ |
| 4 | What surprised us in Postgres-schema multitenancy (Arkency) | High (engineering blog) | https://blog.arkency.com/what-surprised-us-in-postgres-schema-multitenancy/ |
| 5 | pg_tmp ephemeral postgres (eradman.com) | High (project home) | https://eradman.com/ephemeralpg/ |
| 6 | IntegreSQL — managed isolated PG for tests (GitHub) | High (active OSS) | https://github.com/allaboutapps/integresql |
| 7 | pgtestdb — per-test PG isolation (GitHub) | High (active OSS) | https://github.com/peterldowns/pgtestdb |
| 8 | Testcontainers Reusable Containers (Java docs) | Authoritative (vendor) | https://java.testcontainers.org/features/reuse/ |
| 9 | Testcontainers Desktop guide | Authoritative (vendor) | https://testcontainers.com/guides/simple-local-development-with-testcontainers-desktop/ |
| 10 | Neon Branching docs | Authoritative (vendor) | https://neon.com/docs/introduction/branching |
| 11 | Neon Storage architecture | Authoritative (vendor) | https://neon.com/storage |
| 12 | Neon for AI Agent Platforms | Vendor marketing | https://neon.com/use-cases/ai-agents |
| 13 | Supabase Branching (official docs) | Authoritative (vendor) | https://supabase.com/docs/guides/deployment/branching |
| 14 | PlanetScale — Database branching three-way merge | Authoritative (vendor blog) | https://planetscale.com/blog/database-branching-three-way-merge-schema-changes |
| 15 | Cognition — Devin can manage Devins (announcement) | Authoritative (vendor) | https://cognition.ai/blog/devin-can-now-manage-devins |
| 16 | Devin 2.0 deep-dive (Medium, Takafumi Endo) | Medium (independent analysis) | https://medium.com/@takafumi.endo/agent-native-development-a-deep-dive-into-devin-2-0s-technical-design-3451587d23c0 |
| 17 | OpenAI Codex Cloud Environments (docs) | Authoritative (vendor) | https://developers.openai.com/codex/cloud/environments |
| 18 | Cursor — Implementing a secure sandbox for local agents | Authoritative (vendor blog) | https://cursor.com/blog/agent-sandboxing |
| 19 | Cursor 3 Agent-First Interface (InfoQ) | High (independent reporting) | https://www.infoq.com/news/2026/04/cursor-3-agent-first-interface/ |
| 20 | Cursor Background Agents Complete Guide (Morph) | Medium (third-party guide) | https://www.morphllm.com/cursor-background-agents |
| 21 | GitHub Copilot Coding Agent — customize the agent environment | Authoritative (vendor docs) | https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/customize-the-agent-environment |
| 22 | Replit Snapshot Engine | Authoritative (vendor blog) | https://blog.replit.com/inside-replits-snapshot-engine |
| 23 | Replit Agent 4 announcement | Authoritative (vendor blog) | https://blog.replit.com/introducing-agent-4-built-for-creativity |
| 24 | worktree-compose — Zero-config Compose isolation for git worktrees | High (focused OSS) | https://www.worktree-compose.com/ |
| 25 | Penligent — Git Worktrees Need Runtime Isolation for Parallel AI Agent Dev | High (technical analysis) | https://www.penligent.ai/hackinglabs/git-worktrees-need-runtime-isolation-for-parallel-ai-agent-development/ |
| 26 | dockportless — local service router with auto port assignment (GitHub) | Medium (OSS) | https://github.com/mazrean/dockportless |
| 27 | Heroku Review Apps (Dev Center) | Authoritative (vendor docs) | https://devcenter.heroku.com/articles/github-integration-review-apps |
| 28 | Vercel + Neon: a database for every preview environment | Authoritative (vendor blog) | https://neon.com/blog/branching-with-preview-environments |
| 29 | Neon × Vercel managed integration (Neon docs) | Authoritative (vendor docs) | https://neon.com/docs/guides/vercel-native-integration-previews |
| 30 | Docker Compose CLI reference | Authoritative (vendor) | https://docs.docker.com/reference/cli/docker/compose/ |
| 31 | Docker Compose Networking | Authoritative (vendor) | https://docs.docker.com/compose/how-tos/networking/ |
| 32 | Mastering Git Worktrees with Claude Code for Parallel Development (Medium) | Medium (community guide) | https://medium.com/@dtunai/mastering-git-worktrees-with-claude-code-for-parallel-development-workflow-41dc91e645fe |
| 33 | Per-Test Database Isolation in Postgres (conroy.org) | High (technical blog) | https://conroy.org/per-test-database-isolation-in-postgres |
