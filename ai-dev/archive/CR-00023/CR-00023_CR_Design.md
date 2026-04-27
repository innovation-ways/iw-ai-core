# CR-00023: Make `iw item-status` the runtime source of truth for step list and per-step runtime info

**Type**: Change Request
**Priority**: Medium
**Reason**: Tech debt / hardening — discovered via the I-00041 post-mortem (`/iw-item-analyze I-00041`, findings [2] and [3] folded in together). Eliminates a recurring class of agent confusion caused by drift between the on-disk `workflow-manifest.json` design snapshot and the live DB state, AND eliminates the recurring "QvGate catches a format/typecheck error that the implementation step should have caught locally" tax by adding an explicit pre-flight gate to the Implementation prompt template.
**Created**: 2026-04-27
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Description

Make `iw item-status <ID> --json` a true superset of `workflow-manifest.json` for runtime step info, and stamp the on-disk manifest as a non-authoritative design-time snapshot. Agents will then have a single source of truth (the DB via the iw CLI) and the catch-22 where a stale manifest contradicts the DB will go away.

Also folded in: a small change to `Implementation_Prompt_Template.md` (used by backend/frontend/tests/database/api/pipeline-impl agents) requiring a pre-flight `make format` + `make typecheck` + `make lint` before declaring `completion_status: complete`, with the result reported in a new `preflight` field of the Subagent Result Contract. This addresses I-00041 finding [3]: the Backend/Tests steps shipped unformatted code and `object not callable` mypy regressions that the QvGate steps later caught — burning fix-cycle slots on issues a 30-second pre-flight would have surfaced. The two concerns (manifest drift and missing pre-flight) share the same template subsystem and the same review/test cycle, so combining them here avoids a near-certain merge conflict between two CRs touching the same files.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key invariants:

- "PostgreSQL as sole source of truth — no markdown files, no race conditions" (Key Design Decisions)
- The `iw` CLI is the agent-to-DB bridge (Architecture)
- The daemon is read-only against `workflow-manifest.json` — only design skills (`iw-new-*`) and `iw register` write or ingest it.

## Current Behavior

The work item's `workflow-manifest.json` is created by the design skills (`iw-new-feature`, `iw-new-incident`, `iw-new-cr`) and lives at `ai-dev/active/<ID>/workflow-manifest.json`. `iw register --steps-from <manifest>` ingests it once and copies a subset of fields onto `WorkflowStep` rows in the DB:

| Manifest field | Stored on `WorkflowStep`? |
|----------------|---------------------------|
| `step` | ✅ `step_id` |
| `agent` | ✅ `agent_label`, `opencode_agent` |
| `step_type` | ✅ `step_type` (or inferred) |
| `description` | ✅ `description` |
| `step_label` | ✅ `step_label` |
| `prompt` | ❌ (only stored after the daemon writes a launch prompt) |
| `command` (qv-gate) | ❌ — re-read from manifest at every step launch |
| `gate` (qv-gate) | ❌ — re-read from manifest at every step launch |
| `timeout` | ❌ — re-read from manifest at every step launch |

`iw item-status --json` exposes only `step_id`, `label`, `type`, `status` per step (`orch/cli/item_commands.py:612-`).

The manifest sits inside the worktree's `ai-dev/active/<ID>/` next to runtime artifacts (prompts, reports, fix-cycles). Agents naturally explore the directory via Glob, find `workflow-manifest.json`, and read it. When the manifest disagrees with the DB (after design iteration, re-registration, or hand-edits), agents become confused — see I-00041 S14/S15 logs:

- `S14_run1`: `"S14 is not defined in workflow-manifest.json (steps S01-S12 only)"` (DB had 16 steps; on-disk file had 14)
- `S15_run1`: `"File not found: prompts/I-00041_S13_Backend_prompt.md"` — manifest labelled S13 as `backend-impl`, DB had relabelled it to `qv-gate`

The QualityValidation_FIX prompt template reads `scope.allowed_paths` from the manifest — that field is design-time and immutable, so it does not drift.

## Desired Behavior

After CR-00023:

1. `WorkflowStep` rows store everything the daemon and agents need to know about a step: existing columns plus `command`, `gate`, `timeout_secs` (all nullable).
2. `iw register --steps-from <manifest>` populates the new columns from the manifest at ingest, AND rewrites the manifest in place to add a top-level `_note` field stating it is non-authoritative.
3. `iw item-status <ID> --json` returns per-step entries containing every field an agent could possibly need: `step_id`, `step_number`, `agent_label`, `opencode_agent`, `step_type`, `step_label`, `status`, `description`, `prompt_file`, `command`, `gate`, `timeout_secs`.
4. Implementation, CodeReview, CodeReview_Final, and QualityValidation prompt templates each include a one-line "Input Files" hint:
   > For runtime step state (list, status, paths) prefer `iw item-status <ID> --json` — `workflow-manifest.json` is a design-time snapshot and may be out of date.
5. The daemon code paths that read the manifest for `command`/`gate`/`prompt_file` (`orch/daemon/batch_manager.py:_build_claude_prompt`, `orch/daemon/fix_cycle.py:_get_gate_name_and_command`, `orch/daemon/batch_manager.py:_get_baseline_steps`) prefer the DB columns when populated and fall back to the manifest read when columns are NULL (legacy items registered before this CR).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `workflow_steps` table | No `command` / `gate` / `timeout_secs` columns | Three new nullable TEXT/TEXT/INTEGER columns added via Alembic migration |
| `orch/db/models.py:WorkflowStep` | 13 mapped columns | 16 mapped columns (+ `command`, `gate`, `timeout_secs`) |
| `orch/cli/item_commands.py:register` | Stores 6 manifest fields per step | Stores 9 fields; also rewrites manifest in place to add `_note` header |
| `orch/cli/item_commands.py:item_status` | JSON `steps[]` has 4 fields per entry | 12 fields per entry (superset of manifest) |
| `orch/daemon/batch_manager.py:_build_claude_prompt` | Reads `prompt`/`command`/`description` from manifest | Reads from DB columns first; falls back to manifest read if columns NULL |
| `orch/daemon/fix_cycle.py:_get_gate_name_and_command` | Reads `gate`/`command` from manifest | Reads from DB columns first; falls back to manifest read if columns NULL |
| `orch/daemon/batch_manager.py:_compute_qv_baselines` (`_read_workflow_manifest` consumer) | Reads `gate`/`command` per step | Same fallback pattern |
| 4 prompt templates × 2 dirs (`templates/design/` + `ai-dev/templates/`) | No mention of `iw item-status` | One-line "Input Files" hint pointing to `iw item-status` |

### Breaking Changes

- **None.** New columns are nullable (additive). The `_note` key in manifest JSON is an unrecognised key for every current reader (`iw register` only inspects `steps`; daemon only reads `steps` / `scope`; executor scope_gate only reads `scope`) — adding it is safe. JSON consumers of `iw item-status` that read by key (`step_id`, `label`, `status`) continue to work; new keys are appended.

### Data Migration

- **Not required** for in-flight items. Pre-existing `WorkflowStep` rows keep `command` / `gate` / `timeout_secs` NULL. The daemon code paths that consume those fields fall back to the existing manifest read for legacy rows.
- Reversibility: the Alembic migration is straightforward (drop three columns) and is reversible. Dropping the columns loses the populated values for items registered after this CR ships, but the on-disk manifest still contains them — so re-registration or a manual repopulation script could restore.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Alembic migration: add `command`, `gate`, `timeout_secs` columns to `workflow_steps`; update `WorkflowStep` model | — |
| S02 | code-review-impl | Review S01 schema + migration | — |
| S03 | backend-impl | Update `iw register` to populate new columns from manifest at ingest; rewrite manifest in place to add `_note` field | — |
| S04 | code-review-impl | Review S03 register-side ingest + manifest stamping | — |
| S05 | backend-impl | Enrich `iw item-status --json` per-step output with all 12 fields (true superset of manifest) | — |
| S06 | code-review-impl | Review S05 JSON enrichment | — |
| S07 | template-impl | Add one-line `iw item-status` hint to 8 prompt templates (4 in `templates/design/`, 4 mirrors in `ai-dev/templates/`) | — |
| S08 | code-review-impl | Review S07 template edits | — |
| S09 | tests-impl | Unit tests for register-side ingest + manifest stamping; unit tests for `item-status` JSON shape; integration test (round-trip register → item-status returns enriched fields); regression test that daemon fallbacks still work for legacy NULL rows; explicit AC6 regression test (I-00041 S14/S15 scenario) | — |
| S10 | code-review-impl | Review S09 tests | — |
| S11 | code-review-final-impl | Cross-step global review of S01/S03/S05/S07/S09 — verify schema → register → CLI → templates → tests chain holds end-to-end (final review now sees the test coverage map) | — |
| S12 | qv-gate | QV: lint (`make lint`) | — |
| S13 | qv-gate | QV: format (`make format`) | — |
| S14 | qv-gate | QV: typecheck (`make typecheck`) | — |
| S15 | qv-gate | QV: unit tests (`make test-unit`) | — |
| S16 | qv-gate | QV: integration tests (`make allure-integration`) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: `workflow_steps` — add three nullable columns:
  - `command TEXT NULL` — the shell command for `qv-gate` steps (e.g., `make lint`)
  - `gate TEXT NULL` — the gate name for `qv-gate` steps (e.g., `lint`, `format`, `typecheck`)
  - `timeout_secs INTEGER NULL` — per-step timeout override (mirrors the optional `timeout` field in the manifest)
- **Migration notes**: Generate via `alembic revision --autogenerate`. The migration must be reversible (`downgrade()` drops the three columns).

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None (CLI-only change; no HTTP API touched)
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00023/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00023_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00023_S01_Database_prompt.md` | Prompt | Schema migration + model update |
| `prompts/CR-00023_S02_CodeReview_Database_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00023_S03_Backend_prompt.md` | Prompt | Register-side ingest + manifest stamping |
| `prompts/CR-00023_S04_CodeReview_Backend_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00023_S05_Backend_prompt.md` | Prompt | item-status JSON enrichment |
| `prompts/CR-00023_S06_CodeReview_Backend_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00023_S07_Template_prompt.md` | Prompt | Prompt-template hints |
| `prompts/CR-00023_S08_CodeReview_Template_prompt.md` | Prompt | Review S07 |
| `prompts/CR-00023_S09_Tests_prompt.md` | Prompt | Unit + integration tests |
| `prompts/CR-00023_S10_CodeReview_Tests_prompt.md` | Prompt | Review S09 |
| `prompts/CR-00023_S11_CodeReview_Final_prompt.md` | Prompt | Cross-step final review |

QvGate steps S12–S16 use the inline `command` field in the manifest (no prompt files).

Files to be modified by the steps (for batch planner overlap analysis):

- `orch/db/models.py` (S01)
- `orch/db/migrations/versions/<new_revision>.py` (S01)
- `orch/cli/item_commands.py` (S03, S05)
- `templates/design/Implementation_Prompt_Template.md` (S07)
- `templates/design/CodeReview_Prompt_Template.md` (S07)
- `templates/design/CodeReview_Final_Prompt_Template.md` (S07)
- `templates/design/QualityValidation_Template.md` (S07)
- `ai-dev/templates/Implementation_Prompt_Template.md` (S07)
- `ai-dev/templates/CodeReview_Prompt_Template.md` (S07)
- `ai-dev/templates/CodeReview_Final_Prompt_Template.md` (S07)
- `ai-dev/templates/QualityValidation_Template.md` (S07)
- `docs/IW_AI_Core_CLI_Spec.md` (S05 — update `iw item-status` JSON shape documentation)
- `tests/unit/test_item_commands_register.py` or equivalent (S09)
- `tests/unit/test_item_commands_item_status.py` or equivalent (S09)
- `tests/unit/test_template_hints.py` (S09, new file — covers AC5 + AC7)
- `tests/integration/test_register_to_item_status_roundtrip.py` (S09, new file)
- `tests/integration/test_daemon_legacy_fallback.py` (S09, new file — covers AC4)

The S03 and S05 backend changes also touch the daemon read paths to add fallback logic:
- `orch/daemon/batch_manager.py` (S03 — fallback in `_build_claude_prompt` and `_compute_qv_baselines`)
- `orch/daemon/fix_cycle.py` (S03 — fallback in `_get_gate_name_and_command`)

### Scope (for executor scope gate)

```
scope.allowed_paths:
  - orch/db/models.py
  - orch/db/migrations/versions/**.py
  - orch/cli/item_commands.py
  - orch/daemon/batch_manager.py
  - orch/daemon/fix_cycle.py
  - templates/design/Implementation_Prompt_Template.md
  - templates/design/CodeReview_Prompt_Template.md
  - templates/design/CodeReview_Final_Prompt_Template.md
  - templates/design/QualityValidation_Template.md
  - ai-dev/templates/Implementation_Prompt_Template.md
  - ai-dev/templates/CodeReview_Prompt_Template.md
  - ai-dev/templates/CodeReview_Final_Prompt_Template.md
  - ai-dev/templates/QualityValidation_Template.md
  - docs/IW_AI_Core_CLI_Spec.md
  - tests/unit/test_item_commands_register.py
  - tests/unit/test_item_commands_item_status.py
  - tests/unit/test_template_hints.py
  - tests/integration/test_register_to_item_status_roundtrip.py
  - tests/integration/test_daemon_legacy_fallback.py
```

## Acceptance Criteria

### AC1: `iw item-status --json` returns enriched per-step entries for newly-registered items

```
Given a freshly-registered work item whose manifest contains:
  - an implementation step with `prompt: prompts/X_S01_Backend_prompt.md`
  - a qv-gate step with `gate: lint, command: make lint, timeout: 600`
When `iw item-status <ID> --json` is invoked
Then each entry in the `steps` array contains the keys:
  step_id, step_number, agent_label, opencode_agent, step_type,
  step_label, status, description, prompt_file, command, gate, timeout_secs
And the implementation step's entry has `prompt_file = "prompts/X_S01_Backend_prompt.md"`,
  `command = null`, `gate = null`, `timeout_secs = null`
And the qv-gate step's entry has `prompt_file = null`, `command = "make lint"`,
  `gate = "lint"`, `timeout_secs = 600`
```

### AC2: `iw register` stamps the manifest with a non-authoritative `_note` field

```
Given a `workflow-manifest.json` that does NOT contain a `_note` field
When `iw register --steps-from <manifest>` completes successfully
Then the manifest file on disk has been rewritten in place
And the rewritten file's top-level JSON object contains a `_note` key whose
  value is a string mentioning "design-time snapshot" and "iw item-status"
And every existing key (id, type, title, browser_verification, steps, scope, …)
  is preserved with identical contents
And the JSON is valid and re-parseable
```

### AC3: New schema columns are nullable and reversible

```
Given the live orch DB has been upgraded to the head revision shipped by S01
When `\d workflow_steps` is executed via psql
Then the table has columns `command TEXT NULL`, `gate TEXT NULL`, `timeout_secs INTEGER NULL`
And `alembic downgrade -1` cleanly drops those three columns
And `alembic upgrade head` re-applies them
```

### AC4: Daemon falls back to manifest read for legacy NULL rows

```
Given a `WorkflowStep` row with `command = NULL, gate = NULL, timeout_secs = NULL`
  (representing an item registered before this CR)
And the on-disk manifest contains the matching `command`/`gate`/`timeout` fields
When the daemon launches the step (via `_build_claude_prompt`)
Or computes a QV baseline (via `_compute_qv_baselines`)
Or builds a fix-cycle prompt (via `_get_gate_name_and_command`)
Then the daemon reads the value from the on-disk manifest as it does today
And the step launches/runs successfully with the correct command/gate/timeout
```

### AC5: Prompt templates direct agents to `iw item-status` for runtime info

```
Given the 8 prompt template files (4 in `templates/design/`, 4 mirrors in `ai-dev/templates/`)
When the file content is inspected
Then each file's "Input Files" section contains a one-line hint
  recommending `iw item-status <ID> --json` over reading `workflow-manifest.json`
  for runtime step state
And the QualityValidation_FIX templates are NOT modified
  (they correctly read `scope.allowed_paths` which is design-time and immutable)
```

### AC6: I-00041 S14/S15-style scenario no longer panics

```
Given a regression test that simulates the I-00041 S14 scenario:
  - registers an item with N steps in the manifest
  - inserts an additional WorkflowStep row directly into DB (N+1)
  - launches the (N+1)th step
When the agent (or test harness simulating the agent) calls
  `iw item-status <ID> --json`
Then the response contains step (N+1) with status `in_progress`
And the agent does NOT need to read `workflow-manifest.json` to discover
  the step's existence or its launch parameters
```

### AC7: Implementation prompt template requires pre-flight quality gates

```
Given the modified `templates/design/Implementation_Prompt_Template.md` and its
  `ai-dev/templates/` mirror after S07
When the file content is inspected
Then both copies contain a "## Pre-flight Quality Gates (NON-NEGOTIABLE)"
  section that appears BEFORE "## Test Verification" and explicitly lists
  `make format`, `make typecheck`, and `make lint` as required commands
And the Subagent Result Contract example in the template contains a `preflight`
  object with keys `format`, `typecheck`, `lint`
And the two copies (`templates/design/` and `ai-dev/templates/`) are byte-identical
And the section's wording references CR-00023 so future readers can find the
  context for why pre-flight is mandatory
And the FIX / Browser / CodeReview / QV / CodeReview_Final templates do NOT
  contain a "Pre-flight Quality Gates" section (those agents do not write code)
```

## Rollback Plan

- **Database**: Reverse migration is straightforward — `alembic downgrade -1` drops the three new columns. No data loss for any item that was registered before this CR (those rows already had NULL in these columns); items registered after this CR keep their values in the on-disk manifest, so re-registration can restore.
- **Code**: `git revert` the merge commit. The fallback paths in the daemon mean a partial revert (e.g., reverting only the CLI changes but keeping the schema) is also safe — the daemon continues to work via manifest read.
- **Data**: No data loss on rollback. The manifest file on disk is the canonical source for the manifest fields if the DB columns are dropped.

## Dependencies

- **Depends on**: None
- **Blocks**: Future "remove the manifest from worktrees entirely" work — this CR is the prerequisite that makes the DB a true superset.

## TDD Approach

- Unit tests:
  - `tests/unit/test_item_commands_register.py` — register a mock manifest containing `command`/`gate`/`timeout` fields; assert the resulting `WorkflowStep` rows have those fields populated; assert the manifest file was rewritten in place with a `_note` field; assert pre-existing keys are preserved.
  - `tests/unit/test_item_commands_item_status.py` — given a `WorkflowStep` row populated via test fixture, assert `iw item-status --json` returns all 12 keys with the expected values; assert NULL columns become `null` in JSON.
- Integration tests:
  - `tests/integration/test_register_to_item_status_roundtrip.py` — full round-trip: write a manifest to a temp dir, run `iw register --steps-from`, run `iw item-status --json`, assert the returned JSON contains every field from the manifest plus runtime status.
  - `tests/integration/test_daemon_legacy_fallback.py` — insert a `WorkflowStep` row with NULL `command`/`gate`/`timeout_secs` (simulating a pre-CR item) and a matching on-disk manifest; call the daemon's `_build_claude_prompt`, `_compute_qv_baselines`, `_get_gate_name_and_command`; assert each correctly falls back to the manifest read.
- Updated tests:
  - Any existing `tests/unit/test_item_commands*.py` test that asserts the exact shape of `iw item-status --json` will need updating (new keys appended).

## Notes

- **Why not just rewrite the manifest on every daemon mutation?** The daemon doesn't actually mutate the manifest — drift comes from design iteration before/after registration, not mid-run. Stamping the manifest as non-authoritative + making the DB a true superset addresses the root cause. (See I-00041 post-mortem analysis and the Description above.)
- **Why not delete the manifest entirely?** The manifest is consumed by:
  1. `iw register --steps-from` (one-shot at registration)
  2. `executor/scope_gate.py` (reads `scope.allowed_paths` at merge time)
  3. The daemon read paths (which we're making fallback-only here)
  Deleting the file would force restructuring (1) and (2) — out of scope for this CR. Stamping is the minimum-blast-radius fix.
- **Why no QualityValidation_FIX template change?** That template reads `scope.allowed_paths` from the manifest, and `scope` is a design-time field that does not drift. Touching it would be noise.
- **Risk: a future CR adds another manifest field.** If that field is needed at runtime, it must be added to `WorkflowStep` and to the `iw item-status --json` output as part of that CR. Document this contract in `docs/IW_AI_Core_CLI_Spec.md` so it doesn't get forgotten.
- **Why fold finding [3] (pre-flight gates) into this CR rather than ship a separate CR-00024?** Both findings touch the same template subsystem (`templates/design/Implementation_Prompt_Template.md` and its `ai-dev/templates/` mirror) and the same review/test loop (S07 → S08 → S09). A separate CR would have the same +1 file modification footprint AND would race CR-00023 on a guaranteed merge conflict. Folding adds one extra change to S07's brief and one extra acceptance criterion (AC7) — net cost is small.
- **Why does the pre-flight requirement live ONLY in `Implementation_Prompt_Template.md`?** Because that template is the one rendered for `backend-impl`, `frontend-impl`, `tests-impl`, `database-impl`, `api-impl`, `pipeline-impl`, and `template-impl` agents — i.e., every agent that writes code. CodeReview / CodeReview_Final / QualityValidation / QualityValidation_FIX / QVBrowser / FIX templates drive agents that don't write code, so the pre-flight gates don't apply to them.
