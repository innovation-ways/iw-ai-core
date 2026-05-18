# CR-00062: Add Pi (pi.dev) as a third agent runtime alongside `claude-code` and `opencode`

**Type**: Change Request
**Priority**: Medium
**Reason**: Additive expansion of the agent-runtime surface. Today the daemon and executor dispatch only `opencode` and `claude` as one-shot subprocess runtimes. Pi (pi.dev, package `@earendil-works/pi-coding-agent`) is a peer runtime with the same provider-neutral, print-mode CLI shape — wiring it as a third valid value for `cli_tool` gives projects a third option without forcing migration off the existing two. Driven by the user installing Pi locally and wanting it as a selectable runtime in `projects.toml` and the dashboard runtime-override picker.
**Created**: 2026-05-18
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. This CR ships an Alembic migration (data-only `INSERT`s into `agent_runtime_options`), executor-script edits, daemon argv-builder edits, and a new master agents directory. No new Docker usage. The existing testcontainer fixtures in `tests/integration/conftest.py` remain the only allowed exception, and S05 (`tests-impl`) exercises one to prove the pi dispatch path end-to-end.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR **adds one** Alembic revision (S01) that seeds two rows in `agent_runtime_options` and is reversible via `DELETE` in `downgrade()`. There are **no DDL changes** — the table, columns, indexes, and constraints introduced by F-00081 (revision `ff23f562353b`) remain untouched. S01 writes the revision file; the daemon applies it through its normal pre-merge dry-run + post-merge apply pipeline. The S02 `qv-gate migration-check` step enforces `alembic upgrade base→head + create_all parity + downgrade→upgrade round-trip` against a fresh testcontainer before any downstream agent inherits the wrong schema.

## Description

Wire `cli_tool = "pi"` end-to-end as a third agent runtime peer to `claude` and `opencode`. Pi is invoked one-shot via its print mode (`pi -p "$INSTRUCTION" --model "$MODEL"`) — the same `prompt → subprocess → stdout` shape the executor already uses for the other two. The change spans (a) eight dispatch sites in bash and Python that build runtime-specific argv, (b) the `agent_runtime_options` catalogue (two seed rows), (c) the `sync-agents` engine + a new `agents/pi/` master tree mirroring `agents/claude/`, (d) the `project_registry` cli_tool allowlist, and (e) `StepRun` / `Batch` column comments. No projects are switched to pi in this CR — the wiring is proven by unit + integration tests against a stub `pi` binary on `PATH`, and a follow-up cuts a pilot project over once we've seen pi run smoke steps cleanly.

## Project Context

Read the project's `CLAUDE.md` for the orchestration architecture, the executor / daemon split, the cli_tool resolution rules, and the hard rules (testcontainers only for live DB, no `importlib.reload(orch.config)`, no `docker compose up` against the orch DB, FTS DDL hook, `DaemonEvent.event_metadata`). Read `executor/CLAUDE.md` for the executor scripts' Docker/Alembic prohibitions. Read `orch/CLAUDE.md` for the package layout, the daemon module map, and the technology-stack table (SQLAlchemy 2.0 sync, psycopg v3, Alembic 1.13+, Click 8.1+). Read `docs/research/R-00072-pi-dashboard-embedding.md` for Pi's full surface area — but note that R-00072 evaluated **dashboard-chat embedding** (a different problem), recommended *against* Pi for that use case, and its conclusions about RPC/SDK/Lit-components complexity **do not transfer** to this CR's use case (one-shot subprocess executor runtime). What does carry over from R-00072: Pi's provider matrix, skill discovery rules (`.pi/skills/`, `.agents/skills/`, `~/.claude/skills/`, `~/.codex/skills/`), MIT license, and explicit Agent-Skills-standard compliance.

## Current Behavior

The agent-runtime surface today has exactly two valid `cli_tool` values: `opencode` (default) and `claude`. Eight dispatch sites build runtime-specific argv:

1. **Executor — step launch.** `executor/step_executor.sh:130` branches `if [[ "$CLI_TOOL" == "opencode" ]] ... elif [[ "$CLI_TOOL" == "claude" ]] ...` and `else` raises `Unknown CLI tool` and calls `iw_step_fail`.
2. **Executor — auto-merge one-shot.** `executor/step_executor_lib.sh:616` `_run_agent_oneshot()` case-statement matches `claude | claude-code)` and `opencode)`; the F-00084 auto-merge dry-run pipes a prompt on stdin and consumes the resolved output on stdout.
3. **Daemon — initial step argv.** `orch/daemon/batch_manager.py:1466` branches `if resolved_cli_tool == "opencode"` to build `opencode run "$(cat {prompt_file})" --model {model} ...` else falls through to the `claude -p "$(cat {prompt_file})"` form.
4. **Daemon — fix-launch argv wrapper.** `orch/daemon/fix_cycle.py:2206-2230` `_build_fix_launch_argv()` returns `["script", "-qec", inner_command, "/dev/null"]` for `opencode` (PTY allocation required) and `["/bin/sh", "-c", inner_command]` for everything else.
5. **Daemon — fix-cycle inner command.** `orch/daemon/fix_cycle.py:2286` builds the inner command (`opencode run "$(cat …)" --model …` vs `claude -p "$(cat …)" --model …`).
6. **Daemon — doc-job command.** `orch/daemon/doc_job_poller.py:298` branches `if cli_tool == "opencode": cmd = 'opencode run "/{skill} doc-job {job.id}" --dangerously-skip-permissions'` else `'claude -p "/{skill} doc-job {job.id}" --permission-mode bypassPermissions'`.
7. **Service layer — doc service.** `orch/doc_service.py:573` builds a doc-update command and branches the same way (`opencode` vs `claude`).
8. **Runtime catalogue resolver.** `orch/agent_runtime/resolver.py:140` queries `AgentRuntimeOption.cli_tool == cli_tool, model == model, enabled.is_(True)`; the catalogue today contains rows only for `opencode` and `claude` (seeded by F-00081 revision `ff23f562353b` and topped up by `d1e2f3gpt53c` for `openai/gpt-5.3-codex`).

Configuration sites:
- `orch/daemon/project_registry.py:155` resolves `cli_tool: str = entry.get("cli_tool") or iw_config.get("cli_tool", "opencode")` — currently free-form string, no allowlist enforcement.
- `projects.toml` per-project `cli_tool` key (currently absent on all entries — projects rely on the `opencode` default).
- `.iw-orch.json` `cli_tool` fallback for backwards-compat with pre-`projects.toml` projects.

Sync sites:
- `orch/skills/sync_agents.py` `AgentSyncResult` dataclass exposes `claude_agents_synced`, `opencode_agents_synced`, `opencode_commands_synced` integer counters; `sync_agents_and_commands()` copies `agents/claude/*.md → .claude/agents/`, `agents/opencode/*.md → .opencode/agents/`, `commands/*.md → .opencode/commands/`.
- `orch/cli/skills_commands.py:127-150` `sync-agents` CLI emits JSON and human output keyed off those three counters.

Database column comments:
- `orch/db/models.py:815` — `StepRun.cli_tool` comment reads `"LLM CLI tool used: 'opencode' or 'claude'"`.
- `orch/db/models.py:1082` — `Batch.cli_tool` has `server_default=text("'opencode'")` (default unchanged, but the docstring above the column references the same two-value enumeration in surrounding code).

Dashboard:
- `dashboard/routers/runtime_overrides.py:74,167` reads `AgentRuntimeOption` rows generically and emits `{"cli_tool": r.cli_tool, ...}` — **runtime-agnostic; no change needed**. New `pi` rows surface automatically once the seed migration lands.

## Desired Behavior

After this CR ships:

- `cli_tool = "pi"` is a valid value end-to-end. Each of the eight dispatch sites listed above has a `pi` branch that invokes `pi -p "$INSTRUCTION" --model "$MODEL"` (step launch / fix cycle / batch launch / one-shot auto-merge) or `pi -p "/{skill} doc-job {job.id}"` (doc-job / doc-service) with the appropriate flags. Unknown `cli_tool` values continue to fail fast with `iw_step_fail` (not silently fall through to a default).
- `project_registry.py` `_load_project_config()` enforces a code-only allowlist `{"opencode", "claude", "pi"}` and logs a warning + skips any project whose `cli_tool` is outside the allowlist. No DB-level CHECK constraint is added — adding a 4th runtime later stays a one-line code change.
- `agent_runtime_options` catalogue contains two new enabled, non-default rows: `(pi, minimax/MiniMax-M2.7)` display "Pi + MiniMax 2.7" and `(pi, openai/gpt-5.3-codex)` display "Pi + GPT-5.3 Codex". Both `enabled=true`, `is_default=false`, `sort_order` placed after the existing `(opencode, openai/gpt-5.3-codex)` row at `sort_order=15` — so `sort_order=25` and `sort_order=26` respectively. The MiniMax 2.7 default (which is `(opencode, minimax/MiniMax-M2.7)` per the F-00081 seed) is left untouched.
- The cascade resolver in `orch/agent_runtime/resolver.py` resolves `(pi, X)` lookups against the new rows; falls through to the catalogue default if the project picks an unknown `(pi, model)` combination (same behaviour as today for unknown `(opencode|claude, model)` pairs).
- A new master agents directory `agents/pi/` mirrors `agents/claude/` (same 31 agent files, frontmatter adjusted for Pi's extension surface where it differs from Claude's). `iw sync-agents` copies them into `<project>/.pi/agents/` and reports a new `pi_agents_synced` counter in both JSON and human output. Pi's universal skill discovery (`~/.claude/skills/`, `~/.codex/skills/`, `.pi/skills/`, `.agents/skills/`) means the existing `skills/` master tree continues to serve Pi without changes.
- `StepRun.cli_tool` column comment and `Batch.cli_tool` column comment both read `"LLM CLI tool used: 'opencode', 'claude', or 'pi'"`. `Batch.cli_tool.server_default` stays `'opencode'`. No CHECK constraint is added.
- The dashboard runtime-override picker (`GET /project/{project_id}/api/runtime-options`) returns the two new Pi rows alongside the existing options. **No router change is required** — the endpoint already projects whatever rows the catalogue holds.
- A new unit test covers all three argv-builder shapes (`opencode` / `claude` / `pi`). A new integration test exercises the pi dispatch path against a stub `pi` binary placed on `PATH` (writes a fixed string to stdout, exits 0) and verifies that (a) `step_executor.sh` invokes the stub with the right argv, (b) `_run_agent_oneshot` passes prompt-on-stdin and captures stdout, (c) `batch_manager._build_fix_launch_argv("pi", ...)` produces the unwrapped `/bin/sh -c` form (no `script -qec` PTY wrapper — that is opencode-only).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `executor/step_executor.sh:130` | `if opencode` / `elif claude` / `else fail` | three-way: + `elif pi` invoking `pi -p "$INSTRUCTION" --model "$MODEL"` |
| `executor/step_executor_lib.sh:616` `_run_agent_oneshot()` | `claude\|claude-code)` and `opencode)` cases | + `pi)` case piping stdin into `pi -p --model "$model"` |
| `orch/daemon/batch_manager.py:1466` | `if resolved_cli_tool == "opencode"` else claude form | three-way: + `elif == "pi"` building `pi -p "$(cat {prompt_file})" --model {model}` |
| `orch/daemon/fix_cycle.py:2206-2230` `_build_fix_launch_argv()` | opencode → `["script","-qec",inner,"/dev/null"]`; else `["/bin/sh","-c",inner]` | unchanged shape: `pi` falls into the `/bin/sh -c` arm (no PTY wrapper needed) |
| `orch/daemon/fix_cycle.py:2286` | opencode vs claude inner command | + pi inner command form |
| `orch/daemon/doc_job_poller.py:298` | opencode vs claude doc-job command | + pi: `pi -p "/{skill} doc-job {job.id}"` |
| `orch/doc_service.py:573` | opencode vs claude doc-service command | + pi form |
| `orch/daemon/project_registry.py:155` | free-form `cli_tool` string | code-only allowlist `{"opencode","claude","pi"}` with warn-and-skip on unknown values |
| `orch/agent_runtime/resolver.py` | reads rows generically | unchanged code; behaviour expands via new catalogue rows |
| `agent_runtime_options` table | rows for opencode/claude variants only | + two enabled non-default rows: `(pi, minimax/MiniMax-M2.7)` and `(pi, openai/gpt-5.3-codex)` |
| `orch/db/models.py:815` `StepRun.cli_tool` comment | `"… 'opencode' or 'claude'"` | `"… 'opencode', 'claude', or 'pi'"` |
| `orch/db/models.py:1082` `Batch.cli_tool` server_default | `'opencode'` (unchanged) | unchanged; comment-block above column updated to mention pi |
| `orch/skills/sync_agents.py` `AgentSyncResult` | three counters | + `pi_agents_synced: int = 0` |
| `orch/skills/sync_agents.py` `sync_agents_and_commands()` | copies claude + opencode + opencode commands | + copies `agents/pi/*.md → <project>/.pi/agents/` |
| `orch/cli/skills_commands.py:127-150` | JSON + human output for three counters | + JSON key `pi_agents` and human line `Pi agents: {n}`; total includes pi |
| `agents/pi/` master directory | does not exist | created; 31 files mirroring `agents/claude/` (same agent slugs, frontmatter tuned for Pi where it diverges) |
| `dashboard/routers/runtime_overrides.py` | reads catalogue rows generically | **no change** (verified at design time) |

### Breaking Changes

**None.** Existing projects (all four registered: `innoforge`, `iw-ai-core`, `cv`, `Podforger`) keep their current runtime selection. `cli_tool` default in `Batch` stays `'opencode'`. The new `agents/pi/` directory is additive (won't affect `iw sync-agents` for projects that don't use pi — the files are just copied into an unused subdirectory). DB column comments are cosmetic and don't affect runtime behaviour. The allowlist in `project_registry.py` is the only place where invalid input is rejected, and today's two valid values (`opencode`, `claude`) both pass.

### Data Migration

- **Required**: One Alembic revision under `orch/db/migrations/versions/` that runs two `INSERT … ON CONFLICT … DO UPDATE …` statements seeding the Pi catalogue rows. Pattern lifted from `d1e2f3gpt53c_add_gpt_5_3_codex_runtime_option.py`: aligns the SERIAL sequence with `pg_get_serial_sequence(..., true)` before insert (so per-worktree DBs restored from `pg_dump` don't collide on `id`), then inserts with `ON CONFLICT ON CONSTRAINT uq_agent_runtime_options_cli_model DO UPDATE` for idempotency.
- **Reversible**: Yes. `downgrade()` runs two `DELETE FROM agent_runtime_options WHERE cli_tool='pi' AND model=…` statements. No foreign-key cascade concern — the `WorkflowStep.agent_runtime_option_id` / `WorkItem.agent_runtime_option_id` / `Batch.agent_runtime_option_id` FKs use `ON DELETE RESTRICT`, so a downgrade with in-flight items referencing the new rows correctly fails fast with a constraint violation rather than orphaning rows. In practice this only matters if someone has pinned a step/item/batch to a Pi runtime option before downgrade, which is the expected behaviour.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `database-impl` | Alembic revision file under `orch/db/migrations/versions/` seeding the two `(pi, model)` rows; update `StepRun.cli_tool` + `Batch.cli_tool` column comments in `orch/db/models.py` | — |
| S02 | `qv-gate` (`migration-check`) | `make migration-check` round-trip + drift gate (runs `tests/integration/test_migrations_round_trip.py` against a fresh testcontainer) | — (depends on S01) |
| S03 | `pipeline-impl` | Add `pi` branch to all eight dispatch sites (executor + daemon + service); add code-only allowlist `{opencode,claude,pi}` in `project_registry.py` | S04 |
| S04 | `backend-impl` | Create `agents/pi/` master tree (mirror `agents/claude/`); extend `orch/skills/sync_agents.py` (`pi_agents_synced` field, `.pi/agents/` target); extend `orch/cli/skills_commands.py` JSON + human output; no projects.toml changes (per S05 below — pilot is out of scope) | S03 |
| S05 | `tests-impl` | Unit tests for argv builders (all three runtimes, both batch_manager and fix_cycle sites); integration test with stub `pi` binary on PATH that exercises step + fix + auto-merge + doc-job dispatch; sync_agents test that verifies `agents/pi/` copy into `.pi/agents/` and the new counter; project_registry test that exercises the allowlist warn-and-skip path | — (depends on S03, S04) |
| S06 | `code-review-impl` | Per-agent code review of S01/S03/S04/S05 work | — |
| S07 | `code-review-fix-impl` | Apply CRITICAL/HIGH findings from S06 | — |
| S08 | `code-review-final-impl` | Cross-agent global review (integration boundaries: executor↔daemon↔resolver↔dashboard surface) | — |
| S09 | `code-review-fix-final-impl` | Apply CRITICAL/HIGH findings from S08 | — |
| S10 | `qv-gate` (`lint`) | `make lint` | — |
| S11 | `qv-gate` (`quality`) | `make quality` (lint + format-check + mypy) | — |
| S12 | `qv-gate` (`unit-tests`) | `make test-unit` | — |
| S13 | `qv-gate` (`integration-tests`) | `make test-integration` | — |
| S14 | `self-assess-impl` | SelfAssess via `iw-item-analyze` (project `iw-ai-core` has `self_assess = true`) | — |

Agent slugs verified against `skills/iw-workflow/SKILL.md`'s canonical agent table and `executor/step_executor_lib.sh`.

### Database Changes

- **New tables**: None
- **Modified tables**: `agent_runtime_options` — two rows inserted, two `Comment` updates on `StepRun.cli_tool` and `Batch.cli_tool` (both cosmetic; no DDL change)
- **Migration notes**: Follow the `d1e2f3gpt53c` pattern (sequence realignment + `ON CONFLICT … DO UPDATE` for idempotency under `pg_dump` restore into per-worktree DBs). Revision id and down_revision chosen by `alembic revision --autogenerate -m "add_pi_runtime_options"` at S01 time — do not hand-pick. The S02 migration-check gate enforces `upgrade head + create_all parity + downgrade→upgrade round-trip` against a testcontainer before any downstream agent inherits the wrong schema (per CR-00021 + the F-00079 post-mortem).

### API Changes

- **New endpoints**: None
- **Modified endpoints**: `GET /project/{project_id}/api/runtime-options` returns two additional rows once S01 lands — but the endpoint's response *shape* is unchanged; this is data-only.
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None
- `browser_verification` = **false** (backend-only; the new catalogue rows surface in the existing runtime-override picker dropdown via the existing endpoint).

## File Manifest

All files for this work item live under `ai-dev/active/CR-00062/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00062_CR_Design.md` | Design | This document |
| `CR-00062_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the daemon |
| `prompts/CR-00062_S01_Database_prompt.md` | Prompt | S01 — `database-impl` |
| `prompts/CR-00062_S03_Pipeline_prompt.md` | Prompt | S03 — `pipeline-impl` |
| `prompts/CR-00062_S04_Backend_prompt.md` | Prompt | S04 — `backend-impl` |
| `prompts/CR-00062_S05_Tests_prompt.md` | Prompt | S05 — `tests-impl` |
| `prompts/CR-00062_S06_CodeReview_prompt.md` | Prompt | S06 — `code-review-impl` |
| `prompts/CR-00062_S07_CodeReviewFix_prompt.md` | Prompt | S07 — `code-review-fix-impl` |
| `prompts/CR-00062_S08_CodeReview_Final_prompt.md` | Prompt | S08 — `code-review-final-impl` |
| `prompts/CR-00062_S09_CodeReviewFix_Final_prompt.md` | Prompt | S09 — `code-review-fix-final-impl` |
| `prompts/CR-00062_S14_SelfAssess_prompt.md` | Prompt | S14 — `self-assess-impl` |

(S02, S10, S11, S12, S13 are QV gates — command-only, no prompt files.)

Reports are created during execution in `ai-dev/active/CR-00062/reports/`.

## Acceptance Criteria

### AC1: `cli_tool = "pi"` dispatches end-to-end through all eight sites

```
Given a project configured with cli_tool = "pi" in projects.toml
And ai_assistant.default_model = "minimax/MiniMax-M2.7"
And a stub `pi` binary on PATH that echoes a fixed marker to stdout and exits 0
When the daemon launches a workflow step via step_executor.sh
And then a fix cycle via fix_cycle._launch_fix_agent
And then a doc-job via doc_job_poller._build_agent_command
And then an auto-merge one-shot via step_executor_lib.sh _run_agent_oneshot
Then each invocation builds an argv that starts with `pi -p ... --model minimax/MiniMax-M2.7`
And the stub binary's marker appears in the step log / fix-cycle log / doc-job stdout / auto-merge stdout
And no invocation uses the `script -qec ... /dev/null` PTY wrapper (that wrapper is opencode-only per fix_cycle._build_fix_launch_argv)
And no invocation falls through to the claude or opencode branches
```

### AC2: The two new catalogue rows resolve correctly and surface in the dashboard

```
Given S01's migration has been applied to a fresh testcontainer
When agent_runtime/resolver.resolve_runtime() is called with project.cli_tool="pi" and project.model="minimax/MiniMax-M2.7"
Then it returns the row with cli_tool="pi", model="minimax/MiniMax-M2.7", display_name="Pi + MiniMax 2.7", enabled=true, is_default=false
And the same lookup with model="openai/gpt-5.3-codex" returns display_name="Pi + GPT-5.3 Codex"
And a lookup with project.cli_tool="pi", project.model="<unknown>" falls back to the catalogue is_default=true row
And `GET /project/{project_id}/api/runtime-options` lists both new rows alongside the existing options
And the existing default (the MiniMax 2.7 default for opencode per F-00081 seed) is still is_default=true
And `make migration-check` reports upgrade head + create_all parity + downgrade→upgrade round-trip all green
```

### AC3: The agents/pi/ master tree is created, synced, and reported

```
Given S04 has created agents/pi/ mirroring agents/claude/ (same 31 .md files)
And S04 has extended sync_agents_and_commands() and the sync-agents CLI
When `uv run iw sync-agents` is run for a registered project
Then the project's .pi/agents/ directory contains exactly 31 .md files matching agents/pi/
And the CLI human output prints a "Pi agents: 31" line alongside the existing Claude/OpenCode lines
And the CLI --json output includes a "pi_agents" key with value 31
And the AgentSyncResult dataclass has a pi_agents_synced field defaulting to 0
And the total file count printed by the CLI includes pi_agents_synced
And re-running sync-agents is idempotent (file count unchanged, files byte-identical)
```

### AC4: Allowlist enforcement in project_registry

```
Given projects.toml contains a project entry with cli_tool = "<typo>" (e.g., "pii", "piE", "open code")
When the daemon loads project configs via project_registry._load_project_config()
Then a warning is logged naming the project id and the invalid cli_tool value
And the project is skipped (not added to the in-memory registry)
And the daemon continues loading other projects without raising
And projects with cli_tool in {"opencode", "claude", "pi"} load normally
And projects with no cli_tool key fall back to opencode (existing behaviour, unchanged)
```

### AC5: Column comments updated; default unchanged

```
Given S01's migration has run
When pg_dump --schema-only is inspected for the agent_runtime_options, step_runs, and batches tables
Then step_runs.cli_tool COMMENT reads "LLM CLI tool used: 'opencode', 'claude', or 'pi'"
And batches.cli_tool COMMENT reads similarly
And batches.cli_tool DEFAULT is unchanged: 'opencode'::text
And no CHECK constraint exists on either column (allowlist is code-only, by design)
```

### AC6: All QV gates pass

```
Given the daemon launches CR-00062's S10..S13 QV gates
When each gate runs against the patched worktree
Then S10 (lint), S11 (quality), S12 (test-unit), S13 (test-integration) all exit 0
And no new mypy / ruff / format-check error is introduced
And the new tests added by S05 pass (8+ unit-test assertions, 4+ integration-test assertions covering each of the four dispatch surfaces)
```

## Rollback Plan

- **Database**: Run `alembic downgrade -1` to reverse S01's revision. The two Pi catalogue rows are deleted; the column-comment changes are reverted by the same `downgrade()` body. If a workflow step / item / batch has been pinned to a Pi runtime option between merge and rollback, the `ON DELETE RESTRICT` FK fails the downgrade — that's the correct behaviour; manually re-pin the step/item/batch to a non-pi option first, then re-run the downgrade.
- **Code**: Revert the squash-merge commit. The eight dispatch sites lose their `pi` branches, `project_registry.py` loses the allowlist, `orch/skills/sync_agents.py` loses the `pi_agents_synced` field, and the `agents/pi/` master directory is deleted. Per-project state stays clean because no project switched to pi in this CR.
- **Data**: No data loss possible. The `agent_runtime_options` rows being deleted are catalogue rows, not user data. If a project's `.pi/agents/` directory was populated by `iw sync-agents` between merge and rollback, those files remain on disk after rollback (cleanup is manual and harmless — pi reads from many skill paths and won't choke on orphaned agent files).

A partial rollback path also exists if a regression is discovered post-merge for the *catalogue* side only: a single follow-up CR can flip both new rows to `enabled=false` via `UPDATE agent_runtime_options SET enabled=false WHERE cli_tool='pi'` without reverting the executor / daemon dispatch code. The rows then drop out of the dashboard picker (which filters `enabled.is_(True)`) and the cascade resolver falls back to the catalogue default for any item that was using them. The pi dispatch code path stays in place and harmless.

## Dependencies

- **Depends on**: F-00081 (`ff23f562353b_f_00081_agent_runtime_options.py` — established the catalogue table this CR seeds). Already merged.
- **Blocks**: None (no in-flight item is waiting on pi support).

## Impacted Paths

- `executor/step_executor.sh`
- `executor/step_executor_lib.sh`
- `orch/daemon/batch_manager.py`
- `orch/daemon/fix_cycle.py`
- `orch/daemon/doc_job_poller.py`
- `orch/doc_service.py`
- `orch/daemon/project_registry.py`
- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/skills/sync_agents.py`
- `orch/cli/skills_commands.py`
- `agents/pi/**`
- `tests/unit/**`
- `tests/integration/**`
- `ai-dev/active/CR-00062/**`

## TDD Approach

- **RED-first evidence** — S03 and S04 must capture targeted failing-test output before implementation:
  - S03: a unit test that calls a hypothetical `_build_pi_argv()` or equivalent dispatch site with `cli_tool="pi"` and asserts argv starts with `["pi", "-p", ...]`. The RED run fails with `AssertionError` (the dispatch falls through to `claude` today, producing argv starting with `["claude", "-p", ...]`).
  - S04: a unit test that calls `sync_agents_and_commands()` with a `platform_root` containing `agents/pi/dummy.md` and asserts `result.pi_agents_synced == 1`. The RED run fails with `AttributeError: 'AgentSyncResult' object has no attribute 'pi_agents_synced'`.
- **Unit tests** (S05):
  - `tests/unit/test_pi_runtime_dispatch.py` — argv builders for all three runtimes across `batch_manager._build_initial_command`, `fix_cycle._build_fix_inner_command`, `fix_cycle._build_fix_launch_argv`, `doc_job_poller._build_agent_command`, `doc_service._build_command`. Parametrize `cli_tool ∈ {opencode, claude, pi}`.
  - `tests/unit/test_sync_agents_pi.py` — `sync_agents_and_commands()` with a fixture `platform_root` that includes `agents/pi/`. Assert counter, target directory, file content.
  - `tests/unit/test_project_registry_allowlist.py` — `_load_project_config()` with `cli_tool ∈ {opencode, claude, pi, "<typo>"}`. Assert warn-and-skip for typo, success for the three valid values.
- **Integration tests** (S05):
  - `tests/integration/test_pi_dispatch_end_to_end.py` — places a stub `pi` binary on `PATH` (a 3-line bash script that echoes a marker and exits 0), spins a testcontainer, registers a fake project with `cli_tool = "pi"`, invokes `step_executor.sh` directly, asserts the stub was called and the marker appears in the step log. Uses the existing testcontainer fixtures from `tests/integration/conftest.py`. Skip on CI if the stub-PATH mechanism is platform-incompatible (note in test, not silent skip).
- **Updated tests**: None — this is additive. The existing `tests/unit/test_build_fix_launch_argv.py` (or wherever the opencode-vs-claude argv assertion lives) gets a third parametrize case for `pi`, not a rewrite.

## Notes

- **R-00072 use-case mismatch.** The Pi research filed yesterday recommended *against* embedding Pi in the dashboard chat. Its conclusions about RPC subprocess complexity (LF-only JSONL framing, Extension UI Protocol relay, DIY approvals) **do not apply here** — this CR uses Pi's print mode (`pi -p ...`), which is a one-shot subprocess matching the existing claude/opencode shape. R-00072's findings on provider portability, skill discovery, MIT license, and Agent-Skills-standard compliance *do* carry over and are favourable.
- **No pilot project switch.** Per the GO/NO-GO decision, no project is moved to `cli_tool = "pi"` in this CR. A follow-up cuts over a low-traffic project (likely `cv`) once we've seen pi run a smoke step in CI without regressing the existing two-runtime baseline.
- **No DB CHECK constraint.** The allowlist `{opencode, claude, pi}` lives only in `project_registry.py`. Reason: a 4th runtime in the future (Aider? Continue.dev? a self-hosted fork?) stays a 1-line code change instead of a schema migration. Trade-off accepted at design time.
- **`agents/pi/` mirrors `agents/claude/`, not `agents/opencode/`.** Pi's extension surface is closer to Claude's `.claude/agents/*.md` frontmatter convention than to OpenCode's `.opencode/agents/*.md` shape. Some frontmatter fields will need translation (e.g., Pi uses a `skills` array referencing `~/.claude/skills/` and `.pi/skills/`; Claude uses model-specific keys). S04 owns the translation. If a particular agent file genuinely cannot be mapped, S04 may stub it with a one-line frontmatter and a `TODO(CR-00062-followup):` comment pointing to a follow-up — but the count should match agents/claude/ exactly for AC3 to pass.
- **Stub `pi` binary in tests** — to avoid network calls and provider-auth complexity, S05's integration test ships a 3-line bash stub (`#!/usr/bin/env bash; echo "STUB_PI_OUTPUT_$$"; exit 0`) and prepends it to `PATH`. This mirrors the pattern used by `tests/integration/test_opencode_dispatch_e2e.py` (if present) — S05 will confirm during RED-phase. If no comparable opencode-stub test exists, S05 establishes the pattern.
- **Sibling repos** (`iw-doc-plan`, `podforger`, `cv`) pick up the new `agents/pi/` tree only when their next `iw sync-agents` is run — that's out of scope here.
