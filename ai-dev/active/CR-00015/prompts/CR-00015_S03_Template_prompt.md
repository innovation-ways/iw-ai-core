# CR-00015_S03_Template_prompt

**Work Item**: CR-00015 — Remove docker-compose db service foot-gun
**Step**: S03
**Agent**: template-impl

---

## Input Files

- `ai-dev/active/CR-00015/CR-00015_CR_Design.md` — Design (Desired Behavior point 7, AC5, AC6)
- `ai-dev/active/CR-00015/reports/CR-00015_S01_Backend_report.md` — has the list of stale doc references the S01 agent found
- Files you'll update:
  - `README.md` (project root)
  - `CLAUDE.md` (project root)
  - `docs/README.md`
  - `docs/IW_AI_Core_Tech_Stack.md`
  - `docs/implementation/01_foundation/02_config_and_db.md`
- File you'll create: `docs/IW_AI_Core_DB_Setup.md`

## Output Files

- `ai-dev/active/CR-00015/reports/CR-00015_S03_Template_report.md`
- `docs/IW_AI_Core_DB_Setup.md` (new)
- All the doc files listed above, updated

## Context

You're the documentation pass for CR-00015. S01 did the structural change (split compose files + updated `ai-core.sh` / `Makefile`); your job is to make sure every human-facing doc reflects the new structure AND explains WHY the split exists, so future contributors understand the rationale and don't revert it under the assumption that "one compose file is simpler".

Read the design doc — especially the **Current Behavior** section (describes the 2026-04-22 incident) and **Desired Behavior** point 7 + AC5.

## Requirements

### 1. Create `docs/IW_AI_Core_DB_Setup.md`

This is the new single source of truth for DB setup. Target audience: any developer setting up a fresh machine OR trying to understand the production DB config.

Required sections:

#### 1.1 Header + TL;DR

```markdown
# IW AI Core — Database Setup

The orchestration database is a single long-lived PostgreSQL 15 instance on
host port 5433. There are TWO paths to stand it up; pick the one that matches
your context.

| Path | When to use | Data location |
|---|---|---|
| **Production** (raw `docker run`, bind mount) | Any machine where the DB must persist across container replacements | Host bind mount `/opt/postgres/data` |
| **Bootstrap** (compose, named volume) | First-time dev machine with no pre-existing container | Docker volume `iw-ai-core_pgdata` |

**Never run `docker compose up` from a worktree against the orchestration DB.**
See *Why this split exists* below for the incident that shaped this rule.
```

#### 1.2 Production path (primary)

Document the exact raw `docker run` command. Include:

- Pre-flight: ensure `/opt/postgres/data` exists on host with appropriate ownership.
- Credentials source: `.env` (don't hardcode).
- Suggested run command (adapt values as needed from `.env`):

```bash
docker run -d \
  --name postgres \
  --restart unless-stopped \
  -p 5433:5432 \
  -v /opt/postgres/data:/var/lib/postgresql/data \
  -e POSTGRES_DB="$IW_CORE_DB_NAME" \
  -e POSTGRES_USER="$IW_CORE_DB_USER" \
  -e POSTGRES_PASSWORD="$IW_CORE_DB_PASSWORD" \
  -e PGDATA=/var/lib/postgresql/data/pgdata \
  postgres:15-alpine
```

- Post-run: `iw_orch` database + user created via bootstrap SQL if they don't exist (document the SQL if it's not already bootstrapped elsewhere).
- Verification: `./ai-core.sh db status` → accepting connections.
- Identity fingerprint (post-CR-00014): run `uv run iw db-identity show` and add the UUID to `.env` as `IW_CORE_EXPECTED_INSTANCE_ID`.

#### 1.3 Bootstrap path (dev only)

Brief — five lines max, with a warning banner:

```markdown
### Bootstrap (dev only — throwaway DB)

> Use this only when you don't have a pre-existing `postgres` container and
> the DB will be ephemeral (local dev, no important data).

    docker compose -f docker-compose.bootstrap.yml up -d db

This creates a named volume `iw-ai-core_pgdata` (not a bind mount). The
volume is managed entirely by Docker; destroying the container does NOT
destroy the volume, but re-running from a clean state is expected.
```

Note the `-f` flag is mandatory. `docker compose up` without it does nothing (the root `docker-compose.yml` is an intentional stub).

#### 1.4 Why this split exists

```markdown
### Why the split exists

On **2026-04-22**, the default `docker-compose.yml` (which then contained
the `db` service directly) was invoked from a git worktree at
`.worktrees/F-00058/`. Docker Compose uses the cwd basename as its project
name unless overridden, so the invocation created a volume
`f-00058_pgdata` (empty, fresh schema) and a container `iw-ai-core-db`
that took over port 5433. The real orchestration DB — a raw `docker run`
container named `postgres` with a host bind mount at `/opt/postgres/data`
— had been SIGKILLed minutes earlier by an unrelated process. Nothing
detected the swap because the impostor DB had the correct schema and
credentials. 94 work items, 35 batches, 631 step runs, and 66 project
docs silently stopped being written for ~80 minutes.

CR-00014 added an identity-fingerprint check that now catches such a
swap immediately. CR-00015 (this change) removed the underlying
temptation: `docker compose up` from any directory no longer touches
port 5433 because the `db` service has been moved to
`docker-compose.bootstrap.yml`, which requires an explicit `-f` flag.
```

#### 1.5 Quick-reference — common commands

Table of "I want to X" → command, covering: check status, restart DB, tail DB logs, open psql, run migrations. All invocations should go through `./ai-core.sh` if possible; fall through to the raw commands only for ops-emergency paths.

### 2. Update top-level `README.md`

Find the section that references DB setup (search for `make db-up`, `docker compose`, or `./ai-core.sh`). Add or update a short paragraph:

```markdown
### Database

The orchestration DB runs on port 5433 and is NOT managed by the default
`docker-compose.yml`. See [`docs/IW_AI_Core_DB_Setup.md`](docs/IW_AI_Core_DB_Setup.md)
for the two supported setup paths (production bind-mount vs. dev bootstrap)
and the 2026-04-22 incident that shaped this split.

For routine ops, use `./ai-core.sh` — the script knows which compose file
to invoke and will no-op cleanly if the DB is already running.
```

Do NOT break the rest of the README.

### 3. Update top-level `CLAUDE.md`

Locate the **Live DB Setup** section (around line 50-60). Replace or extend it with:

```markdown
## Live DB Setup

**Port 5433** — pre-existing `postgres` Docker container (NOT docker-compose managed in production).

The default `docker-compose.yml` at the project root is **intentionally empty**.
The `db` service lives in `docker-compose.bootstrap.yml` and is invoked only
with `-f docker-compose.bootstrap.yml up -d db` — never implicitly. This
prevents `docker compose up` from a worktree creating a rogue empty volume
that clobbers the production DB (the 2026-04-22 data-loss incident).

See [`docs/IW_AI_Core_DB_Setup.md`](docs/IW_AI_Core_DB_Setup.md) for both setup paths.

**Never run `docker compose up` or `docker compose up -d db` in any form
against the orchestration DB.** Always go through `./ai-core.sh db start`.
```

Also find the **Critical Rules** bulleted list near the top and add:

```markdown
- **NEVER** run `docker compose up` (with or without `-d db`) against the
  orchestration DB from any directory — the default compose file is empty
  and the bootstrap file requires an explicit `-f` flag. Use `./ai-core.sh
  db start` instead. See `docs/IW_AI_Core_DB_Setup.md`.
```

### 4. Update `docs/README.md`

The docs index. Add an entry for `IW_AI_Core_DB_Setup.md` under whatever grouping is appropriate (likely "Setup" or "Operations"). Preserve the rest of the index.

### 5. Update `docs/IW_AI_Core_Tech_Stack.md`

Find the section about Postgres / Docker / DB. Replace any mention of `docker compose up -d db` with:

- A brief summary: "Production = raw `docker run` with bind mount at `/opt/postgres/data`. Dev-bootstrap path = `docker compose -f docker-compose.bootstrap.yml up -d db`."
- A pointer to `docs/IW_AI_Core_DB_Setup.md`.

Preserve any other tech-stack content.

### 6. Update `docs/implementation/01_foundation/02_config_and_db.md`

This is the step-by-step implementation guide. Any `docker compose up -d db` command gets replaced with `docker compose -f docker-compose.bootstrap.yml up -d db` OR (preferred) `./ai-core.sh db start`. Add a short sidebar:

```markdown
> **Note**: The default `docker-compose.yml` was split into a bootstrap file
> after the 2026-04-22 incident. See `docs/IW_AI_Core_DB_Setup.md`.
```

### 7. Grep for stray references

After all edits, run:

```bash
grep -rn "docker compose up.*db\|docker-compose up.*db" . \
  --include="*.md" --include="*.sh" --include="Makefile" --include="*.yml" \
  --exclude-dir=.git --exclude-dir=.worktrees --exclude-dir=node_modules \
  --exclude-dir=.venv --exclude-dir=ai-dev/active/CR-00015
```

Any hit that doesn't include `-f docker-compose.bootstrap.yml` is a miss — fix it.

Note: `.worktrees/` is excluded because those are git-worktree copies that will rebase. `ai-dev/active/CR-00015/` is excluded because this CR's own prompts discuss the old pattern for context (they're allowed to).

### 8. The "WHY" must be present in every doc

Checklist after all edits — each of these five files has a short paragraph (or sidebar) naming the 2026-04-22 incident AND pointing to `docs/IW_AI_Core_DB_Setup.md`:

- `README.md` ✅
- `CLAUDE.md` ✅
- `docs/README.md` (brief — one-line entry + one-line summary is fine)
- `docs/IW_AI_Core_Tech_Stack.md`
- `docs/implementation/01_foundation/02_config_and_db.md`

## Project Conventions

- Markdown style: match existing headers, code-block fences (triple-backtick ```bash). Line widths: don't enforce — match the file.
- Link style: relative paths (`docs/X.md`) not absolute.
- No HTML. Pure CommonMark.
- No emoji in technical docs unless existing doc uses them.

## TDD Requirement

Documentation work has no automated tests — S05 does a grep-based verification. Your deliverable is correct, clear, discoverable prose.

## Test Verification (NON-NEGOTIABLE)

1. `make lint` — pass (markdown is usually not linted but ensure no shell syntax leaks).
2. Run the grep from §7 and confirm zero stale references.
3. Human read-through: open `docs/IW_AI_Core_DB_Setup.md` and confirm a new dev could follow it end-to-end.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "template-impl",
  "work_item": "CR-00015",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "docs/IW_AI_Core_DB_Setup.md",
    "README.md",
    "CLAUDE.md",
    "docs/README.md",
    "docs/IW_AI_Core_Tech_Stack.md",
    "docs/implementation/01_foundation/02_config_and_db.md"
  ],
  "tests_passed": true,
  "test_summary": "grep for stale references returned zero hits",
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00015 --step S03
# document ...
uv run iw step-done CR-00015 --step S03 --report ai-dev/active/CR-00015/reports/CR-00015_S03_Template_report.md
```
