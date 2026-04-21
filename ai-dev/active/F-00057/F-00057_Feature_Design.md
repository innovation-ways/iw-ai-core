# F-00057: `iw oss` CLI + DB persistence for OSS compliance workflow

**Type**: Feature
**Priority**: High
**Created**: 2026-04-21
**Status**: Draft

---

## Description

Adds an `iw oss` command group (`install`, `scan`, `prepare`, `publish`, `enable`, `disable`, `status`) that wraps the existing `iw-oss-publish` Skill's Python orchestrator (`.claude/skills/iw-oss-publish/scripts/scan.py`) and persists scan findings, tool-run outcomes, and per-project OSS state into three new database tables so the upcoming dashboard OSS view (F-B, to be filed) can query them. Backend-only — no frontend, API, pipeline, or template changes.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules (Postgres port 5433, testcontainer-only for tests, `DaemonEvent.metadata` → `event_metadata`, never reload `orch.config`, etc.).

## Scope

### In Scope

- Alembic migration adding `project.oss_enabled` boolean and creating tables `oss_scan`, `oss_finding`, `oss_tool_run`.
- SQLAlchemy ORM models for the new tables and a field on `Project`.
- New backend service module `orch/oss/` with: scan orchestrator (async subprocess), persistence writer, Tier-1 tool-availability probe, config writer.
- New CLI module `orch/cli/oss_commands.py` exposing `install`, `scan`, `prepare`, `publish`, `enable`, `disable`, `status` subcommands with `--project <id>` and `--json` flags where applicable.
- Integration tests (Postgres testcontainer): migration apply/rollback, service module, CLI commands, persistence round-trip.

### Out of Scope

- HTTP API endpoints (F-B adds these).
- Dashboard HTML / htmx / CSS.
- Quality / Tests status domains (OSS-only for now; future separate work).
- Modifying `scripts/scan.py` itself — this Feature treats the skill's entry point as a black box wrapped via subprocess.
- Running the skill's tool installer under `sudo` or modifying system package state.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Alembic migration + ORM models (`oss_scan`, `oss_finding`, `oss_tool_run`) + `Project.oss_enabled` | — |
| S02 | code-review-impl | Review S01 (schema correctness, FK / index choices, migration reversibility, ORM conventions) | — |
| S03 | backend-impl | `orch/oss/` service module: `scanner.py`, `persistence.py`, `tool_probe.py`, `config_writer.py`, `__init__.py` | — |
| S04 | code-review-impl | Review S03 (subprocess hygiene, no blocking calls in event loop, persistence atomicity, error paths) | — |
| S05 | backend-impl | CLI: `orch/cli/oss_commands.py` (Click group + 7 subcommands) + register in `orch/cli/main.py` | — |
| S06 | code-review-impl | Review S05 (CLI patterns match existing `project_commands.py` / `doc_commands.py`, error output, exit codes) | — |
| S07 | tests-impl | Integration tests in `tests/integration/` using Postgres testcontainer per `tests/CLAUDE.md` | — |
| S08 | code-review-impl | Review S07 (no live-DB usage, correct testcontainer setup, FTS trigger install, fixtures match existing patterns) | — |
| S09 | code-review-final-impl | Global cross-step review (DB → backend → CLI → tests consistency, no leftover TODOs, acceptance criteria coverage) | — |
| S10 | qv-gate | `make lint` | — |
| S11 | qv-gate | `uv run ruff format --check .` | — |
| S12 | qv-gate | `uv run mypy orch/` | — |
| S13 | qv-gate | `make test-unit` | — |
| S14 | qv-gate | `make test-integration` | — |

### Database Changes

- **New tables**: `oss_scan`, `oss_finding`, `oss_tool_run`.
- **Modified tables**: `project` (add `oss_enabled BOOLEAN NOT NULL DEFAULT false`).
- **Migration notes**: Alembic autogenerate + hand-written DDL for the enum types (scan status, finding severity, finding status). Migration must be downgradeable (drop tables, drop column, drop enums).

**`oss_scan` columns**:
- `id BIGSERIAL PRIMARY KEY`
- `project_id` FK → `project.id`, NOT NULL, `ON DELETE CASCADE`
- `started_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `completed_at TIMESTAMPTZ NULL`
- `status` ENUM(`pending`, `running`, `complete`, `error`) NOT NULL
- `mode` ENUM(`scan`, `make_oss`, `publish`) NOT NULL DEFAULT `scan`
- `exit_code INT NULL`
- `head_sha TEXT NULL` (captured at scan start)
- `pill_color` ENUM(`green`, `yellow`, `red`, `gray`) NULL (computed at completion)
- `summary_json JSONB NULL` (counts-by-severity)
- `error_message TEXT NULL`
- Indexes: `(project_id, started_at DESC)` for "latest-per-project" queries.

**`oss_finding` columns**:
- `id BIGSERIAL PRIMARY KEY`
- `scan_id` FK → `oss_scan.id`, NOT NULL, `ON DELETE CASCADE`
- `check_id TEXT NOT NULL` (e.g., `OSS-LIC-01`)
- `severity` ENUM(`MUST`, `SHOULD`, `MAY`, `INFO`) NOT NULL
- `status` ENUM(`pass`, `fail`, `skip`, `human_required`) NOT NULL
- `domain TEXT NOT NULL` (e.g., `license`, `secrets`)
- `summary TEXT NOT NULL`
- `detail TEXT NULL`
- `remediation TEXT NULL`
- `auto_fix_available BOOLEAN NOT NULL DEFAULT false`
- `osps_control TEXT NULL`
- `tool TEXT NULL`
- `evidence_json JSONB NULL`
- Indexes: `(scan_id)`, `(scan_id, severity, status)` for report rendering.

**`oss_tool_run` columns**:
- `id BIGSERIAL PRIMARY KEY`
- `scan_id` FK → `oss_scan.id`, NOT NULL, `ON DELETE CASCADE`
- `tool TEXT NOT NULL` (e.g., `gitleaks`, `syft`)
- `version TEXT NULL`
- `status` ENUM(`ok`, `failed`, `missing`, `skipped`) NOT NULL
- `started_at TIMESTAMPTZ NOT NULL`
- `runtime_ms INT NULL`
- `exit_code INT NULL`
- `output_summary TEXT NULL` (first 2KB of stdout/stderr)
- Indexes: `(scan_id)`.

### API Changes

None — F-B adds HTTP endpoints.

### Frontend Changes

None — F-B adds the dashboard view.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00057/F-00057_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00057/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/F-00057/prompts/F-00057_S01_Database_prompt.md` | Prompt | S01 — migration + ORM models |
| `ai-dev/active/F-00057/prompts/F-00057_S02_CodeReview_prompt.md` | Prompt | S02 — review S01 |
| `ai-dev/active/F-00057/prompts/F-00057_S03_Backend_prompt.md` | Prompt | S03 — `orch/oss/` service module |
| `ai-dev/active/F-00057/prompts/F-00057_S04_CodeReview_prompt.md` | Prompt | S04 — review S03 |
| `ai-dev/active/F-00057/prompts/F-00057_S05_Backend_prompt.md` | Prompt | S05 — CLI subcommands |
| `ai-dev/active/F-00057/prompts/F-00057_S06_CodeReview_prompt.md` | Prompt | S06 — review S05 |
| `ai-dev/active/F-00057/prompts/F-00057_S07_Tests_prompt.md` | Prompt | S07 — integration tests |
| `ai-dev/active/F-00057/prompts/F-00057_S08_CodeReview_prompt.md` | Prompt | S08 — review S07 |
| `ai-dev/active/F-00057/prompts/F-00057_S09_CodeReview_Final_prompt.md` | Prompt | S09 — global review |

**Source files created / modified** (so the batch planner can detect conflicts):

- `orch/db/migrations/versions/{hash}_add_oss_tables.py` (new)
- `orch/db/models.py` (modified — add `Project.oss_enabled`, new `OssScan`, `OssFinding`, `OssToolRun` classes)
- `orch/oss/__init__.py` (new)
- `orch/oss/scanner.py` (new)
- `orch/oss/persistence.py` (new)
- `orch/oss/tool_probe.py` (new)
- `orch/oss/config_writer.py` (new)
- `orch/cli/oss_commands.py` (new)
- `orch/cli/main.py` (modified — register `oss` group)
- `tests/integration/test_oss_migration.py` (new — S01)
- `tests/integration/test_oss_scanner.py` (new — S03)
- `tests/integration/test_oss_persistence.py` (new — S03)
- `tests/unit/test_oss_tool_probe.py` (new — S03)
- `tests/unit/test_oss_config_writer.py` (new — S03)
- `tests/integration/test_oss_cli.py` (new — S05)
- `tests/integration/test_oss_boundary.py` (new — S07)
- `tests/integration/test_oss_freshness.py` (new — S07)

Reports are created during execution in `ai-dev/active/F-00057/reports/`.

## Acceptance Criteria

### AC1: Scan persists to DB and exposes JSON status

```
Given   a registered project with oss_enabled=true and the iw-oss-publish Skill synced
When    I run `iw oss scan --project iw-ai-core`
Then    scripts/scan.py runs as a subprocess against the project's repo path,
        a new oss_scan row is inserted with head_sha, exit_code, status='complete',
        all emitted findings are inserted into oss_finding,
        and one oss_tool_run row per Tier-1 tool is inserted
And     `iw oss status --project iw-ai-core --json` returns
        {"exit_code", "pill_color", "head_sha", "stale": false,
         "counts": {"must_pass", "must_fail", "must_human_required",
                    "should_pass", "should_fail", "should_human_required",
                    "may_pass", "may_fail", "may_human_required"}}
        (all severity × status combinations the orchestrator emits; `skip`
        is omitted because skipped checks are already captured in oss_tool_run)
```

### AC2: Tool availability probe without install

```
Given   a machine missing gitleaks and ripgrep
When    I run `iw oss install --dry-run`
Then    stdout lists the missing tools and the exact install command per tool
        (from scripts/install_tools.sh's ensure function)
And     no files are modified, no tools are installed
```

### AC3: `iw oss install` runs the installer script

```
Given   a machine with some missing Tier-1 tools and the user has confirmed
When    I run `iw oss install`
Then    scripts/install_tools.sh is invoked and its stdout/stderr is streamed
And     the command returns the installer's exit code
```

### AC4: `iw oss enable` flips flag and writes config

```
Given   a registered project iw-ai-core with oss_enabled=false
When    I run `iw oss enable --project iw-ai-core`
Then    project.oss_enabled becomes true in the DB
And     {project_root}/.iw/oss-publish.toml is written with the resolved config
        (company_legal_name, license defaults, etc.)
And     running the command a second time with no file changes is idempotent
        (same content, no error)
And     running the command when .iw/oss-publish.toml exists with differing
        content (hand-edited by the user) fails with exit 2 and a message
        pointing to --force; passing --force overwrites the file
```

### AC5: HEAD freshness detection

```
Given   an oss_scan row with head_sha = "abc123"
When    the project HEAD has advanced to "def456" (git rev-parse HEAD returns def456)
And     I run `iw oss status --project iw-ai-core --json`
Then    response includes "stale": true
And     pill_color reflects the last scan's verdict but a warning flag indicates staleness
```

### AC6: CLI help is discoverable

```
Given   the iw CLI is installed
When    I run `iw oss --help`
Then    all 7 subcommands are listed with one-line descriptions
And     `iw oss <sub> --help` prints per-command usage
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Scan on project with `oss_enabled=false` | `iw oss scan --project X` | Informative error "OSS not enabled for X; run `iw oss enable` first"; exit 2; no DB writes |
| Scan subprocess exits 2 (setup error) | Missing gitleaks | Persist `oss_scan.status='error'`, `exit_code=2`, `error_message=...`; persist any `oss_tool_run` rows that ran; no `oss_finding` rows |
| Scan on unregistered project | `--project does-not-exist` | Exit 2 with "project not found"; no DB writes |
| `iw oss enable` on non-git directory | Registered project whose path is not a git repo | Exit 2 with "path X is not a git repo"; no DB writes; no `.toml` write |
| `iw oss enable` with hand-edited `.toml` | Existing `.iw/oss-publish.toml` differs from rendered default | Exit 2 with "refusing to overwrite; pass --force"; flag unchanged; file unchanged |
| `iw oss enable --force` with hand-edited `.toml` | Same as above but `--force` set | File overwritten with rendered default; flag set to true; exit 0 |
| Re-running `scan` at the same HEAD | Identical `head_sha` as prior scan | New `oss_scan` row created (history preserved); pill_color reflects new scan |
| Concurrent scans for the same project | Two `iw oss scan` invocations overlap | Both scans create separate rows; no lock contention (DB FKs prevent orphans) |
| Missing Tier-1 tool during scan | gitleaks absent at scan time | Persist `oss_tool_run` with `status='missing'`; scan proceeds; dependent checks report `status='skip'` in oss_finding |
| `iw oss status` with no prior scans | Project never scanned | Return `{"pill_color": "gray", "exit_code": null, "head_sha": null}`; exit 0 |
| `scan.py` emits malformed JSON | Orchestrator bug | Persist `oss_scan.status='error'`, `error_message` contains parse error; no `oss_finding` rows |

## Invariants

1. Every `oss_finding` row has exactly one parent `oss_scan` row (FK enforced, `ON DELETE CASCADE`).
2. Every `oss_tool_run` row has exactly one parent `oss_scan` row (FK enforced).
3. `oss_scan.pill_color` is derivable from its findings: `must_fail > 0 OR must_human_required > 0 → red`; else `should_fail > 0 OR should_human_required > 0 → yellow`; else `green`; `null → gray`.
4. `oss_scan.head_sha` is set at scan start (before subprocess invocation), not at completion — so a mid-scan commit does not invalidate the claim.
5. `.iw/oss-publish.toml` contents written by `iw oss enable` match the defaults from `lib/config.py` when no project overrides exist; `iw oss enable` never silently overwrites user-edited content (requires `--force`).
6. Deleting a project cascades to its `oss_scan` rows (and transitively to `oss_finding` + `oss_tool_run`).
7. `status --json` output keys are stable across versions (dashboard consumers depend on this shape).

## Dependencies

- **Depends on**: `iw-oss-publish` skill (merged: commits `ee86f6d`, `4b67697`).
- **Blocks**: F-B (dashboard OSS view — to be filed after F-00057 merges).

## TDD Approach

**Unit tests** (isolated from DB where possible):
- `tool_probe.py`: version parsing, binary-alias lookup, missing-tool detection.
- `config_writer.py`: default-only render vs overrides, idempotent rewrite.

**Integration tests** (Postgres testcontainer per CLAUDE.md):
- **Migration**: apply migration creates all 3 tables + column; downgrade reverses them.
- **Persistence**: insert a scan → findings → tool runs; FK cascade deletes findings when scan deleted; cascade deletes scans when project deleted.
- **Scanner**: `orch.oss.scanner.run_scan()` invokes `scripts/scan.py` against a scratch git repo fixture, captures stdout/exit code, persists results.
- **CLI**:
  - `iw oss enable` writes `.toml` + flips flag.
  - `iw oss scan` persists findings (check row counts match emitted JSON).
  - `iw oss status --json` returns the contract shape in AC1 / AC5.
  - `iw oss install --dry-run` enumerates missing tools without invocation.

**Edge cases** (from Boundary Behavior table — one test per row):
- Scanning a disabled project → error + no writes.
- Subprocess exit 2 → scan status='error'.
- Unregistered project → error.
- Non-git directory on enable → error.
- Re-run at same HEAD → new row + history preserved.
- Missing tool → tool_run.status='missing'.
- No prior scans → gray pill.
- Malformed orchestrator output → scan status='error'.

## Notes

- The skill's entry point is `scripts/scan.py` with modes `scan` / `make_oss` / `publish`. The service module (`orch/oss/scanner.py`) invokes it via `asyncio.create_subprocess_exec` and parses the JSON it writes to `.iw/oss-publish-findings.json` — we read the artifact file rather than parsing stdout so we get the full structured output.
- **Skill path resolution**: `orch.oss` always uses iw-ai-core's canonical copy of the skill at `<iw-ai-core repo root>/.claude/skills/iw-oss-publish/`. The CLI resolves this via `orch.config` (project root) rather than the synced-to-project copy. Rationale: the orchestrator and skill evolve together; pinning per-project would create drift.
- **Importing the skill's `TIER1` list**: since `iw-oss-publish` contains a hyphen (not importable via dotted path), `orch/oss/tool_probe.py` loads `scripts/lib/tools.py` via `importlib.util.spec_from_file_location(...)` given an absolute path. No `sys.path` mutation.
- The orchestrator already persists files to `.iw/` in the project directory. The DB layer is a secondary index for dashboard performance — files remain canonical.
- We deliberately do NOT add a `sudo` path to `iw oss install`. The install script already uses `gh release download` fallbacks that avoid sudo; when it genuinely needs sudo (apt), it fails with a clear message rather than prompting.
- Future freshness model: F-B will compare `oss_scan.head_sha` with the current `git rev-parse HEAD` on dashboard render. This Feature only persists `head_sha`; the dashboard computes staleness.
- For `iw oss prepare` (make_oss) and `iw oss publish`: these write to the target repo's filesystem (prep branch + shell scripts in `.iw/`). The CLI runs as the developer — filesystem permissions are fine. When F-B invokes these via the dashboard, access controls will be added at that layer.
- History retention: this Feature preserves every scan. A future cleanup job (not in scope) can prune old rows per project.
