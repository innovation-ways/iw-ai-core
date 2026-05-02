# F-00078: Per-project self-assessment step with copy-paste fix prompts

**Type**: Feature
**Priority**: Medium
**Created**: 2026-05-02
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

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

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

---

## Description

Adds a new opt-in workflow step `self_assess` that runs after the last review/QV gate and before squash-merge. The step invokes the existing `iw-item-analyze` skill against the just-completed item, surfaces process findings (severity-tagged, with per-finding `target: iw-ai-core | project`), and emits ready-to-paste `/iw-new-incident` and `/iw-new-cr` prompts the human can drop into Claude Code or opencode. The step is **purely informational** — failures never block the merge — and findings are rendered as a new "Self-Assessment" section appended to the existing Execution Report tab, only when the project has opted in via `projects.toml`.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Especially relevant: `orch/CLAUDE.md` (orchestration package layout, daemon modules, StepType enum), `dashboard/CLAUDE.md` (templates/fragments pattern, htmx, server-rendered UI), and `docs/IW_AI_Core_Agent_Constraints.md` (R1/R2 rules).

Existing precedents this feature mirrors:
- **`browser_verification`** opt-in step: project flag → manifest field → step type → daemon hooks (`orch/daemon/browser_env.py`, `orch/daemon/step_monitor.py`, `is_browser_verification_step`).
- **Project flag plumbing**: `orch/daemon/project_registry.py:_build_project_config` reads top-level fields from `projects.toml` entries (e.g., `enabled`, `services`).
- **Execution Report assembly**: `orch/daemon/execution_report.py` builds an `ExecutionReportData` dataclass; the dashboard renders it via `dashboard/templates/fragments/item_execution_report.html`.

## Scope

### In Scope

- New `self_assess` value on the `StepType` enum + Alembic migration adding it to the PostgreSQL `step_type` enum.
- New per-project flag `self_assess` in `projects.toml` entries (default `false`); read by `orch/daemon/project_registry.py` into a new `ProjectConfig.self_assess_enabled: bool` field.
- New helper module `orch/self_assess.py` with: dataclasses for findings + report, JSON parser for the structured findings file, helper to detect a self_assess step, soft-step normalization helper.
- Soft-step semantics in the daemon: when a `self_assess` step terminates with `failed`, the batch_item progression coerces it to `completed` so the merge proceeds; the row still records the actual run status for the report.
- New canonical agent slug `self-assess-impl`. Registration deliverables:
  - `executor/step_executor_lib.sh` — add cases in `get_step_type()` (returns `"implementation"` — same launch path as other LLM agents) and `get_agent_label()` (returns `"SelfAssess"` for report filename consistency).
  - `skills/iw-workflow/SKILL.md` — extend the canonical agent-mapping table with `| SelfAssess | self-assess-impl |`.
  - The slug uses the standard `*-impl` suffix and runs through the standard `step_executor.sh` path (no custom lifecycle like `browser_verification`).
- `iw step-done` payload extension: a new `--analysis-json` flag accepts a path to the structured findings JSON. The flag is validated (sidecar convention + sibling-of-report) but **not persisted in a new column** — the dashboard discovers the JSON via `findings_path_for(StepRun.report_file)`. See AC7 and Notes for the full rationale.
- Execution Report extension: `assemble_execution_report()` loads the findings JSON when present and includes a new `self_assessment: SelfAssessmentData | None` field on `ExecutionReportData`. The Jinja2 fragment appends a "Self-Assessment" section under the existing Retry Timeline when populated.
- Skill migration: `skills/iw-item-analyze/SKILL.md` becomes OpenCode-compatible (frontmatter cleaned of `allowed-tools` and `argument-hint`; `$ARGUMENTS` replaced with the `IW_ITEM_ID` env var that the executor exports). Output contract is updated: instead of chatting findings, the skill now writes `<ID>_self_assess_report.md` (narrative) and `<ID>_self_assess_findings.json` (structured) into the worktree's reports directory, and per-finding includes a `target: iw-ai-core | project` field, a `paste_prompt` string, and `coverage_notes` for log-size honesty.
- Design-skill updates (`skills/iw-new-feature/SKILL.md`, `skills/iw-new-cr/SKILL.md`, `skills/iw-new-incident/SKILL.md`): when generating manifests, read `projects.toml` and inject the `self_assess` step (just before the QV gate block) when the project's `self_assess` flag is `true`. Add `templates/design/SelfAssess_Prompt_Template.md`.
- Sync the migrated skill body and updated design skills to `.claude/skills/` and `ai-dev/templates/` so worktree agents pick them up.

### Out of Scope

- A separate "Analysis Report" tab — extends the existing Execution Report tab instead (per F-00078 scope decision).
- A `iw item-digest` CLI helper for pre-summarizing oversized logs — the skill body itself instructs the agent to use selective reads (`tail`, `head`, `grep`) and declare gaps via `coverage_notes`. A digest CLI is a follow-up if real usage shows the heuristic is insufficient.
- Per-batch or system-wide `self_assess` toggle — flag is per-project only.
- Auto-filing of `/iw-new-incident` / `/iw-new-cr` based on the findings — the prompts are surfaced for human copy-paste, never auto-executed.
- Retroactive analysis of items finished before the flag was enabled — only items whose manifests include the step at design time get analyzed.
- A new DB column on `WorkItem` for findings — findings live on disk in the per-item reports dir; the dashboard reads them at render time. Avoids schema churn.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `self_assess` to `StepType` enum + Alembic migration extending the PostgreSQL `step_type` enum | — |
| S02 | code-review-impl | Review S01 (database) | — |
| S03 | backend-impl | (a) `ProjectConfig.self_assess_enabled` + `_build_project_config` reads `self_assess` from `projects.toml`; (b) `orch/self_assess.py` with findings dataclasses + JSON parser + helpers; (c) soft-step semantics in step transition + batch_item progression; (d) `iw step-done --analysis-json` flag plumbing; (e) register `self-assess-impl` slug in `executor/step_executor_lib.sh` (`get_step_type` and `get_agent_label`); (f) ensure `IW_ITEM_ID` is exported by `executor/step_executor.sh` to the agent process environment | — |
| S04 | code-review-impl | Review S03 (backend) | — |
| S05 | frontend-impl | (a) `assemble_execution_report` loads self_assess data; (b) `dashboard/templates/fragments/item_execution_report.html` appends Self-Assessment section; (c) clipboard buttons for copy-paste prompts | — |
| S06 | code-review-impl | Review S05 (frontend) | — |
| S07 | template-impl | (a) Migrate `skills/iw-item-analyze/SKILL.md` to OpenCode-compatible + new output contract; (b) update `skills/iw-new-feature/`, `skills/iw-new-cr/`, `skills/iw-new-incident/` to inject the `self-assess-impl` step when project flag is on; (c) add `templates/design/SelfAssess_Prompt_Template.md`; (d) extend the canonical agent table in `skills/iw-workflow/SKILL.md` with `self-assess-impl`; (e) sync to `.claude/skills/` and `ai-dev/templates/` | S05 (no overlap) |
| S08 | code-review-impl | Review S07 (skills + templates) | — |
| S09 | tests-impl | Integration: projects.toml flag round-trip; daemon treats self_assess failure as soft (item proceeds to merge); execution_report assembly includes findings; dashboard fragment renders correctly with/without findings; design skills inject step when flag on / omit when off. Unit: findings JSON parser + self_assess helper module | — |
| S10 | code-review-impl | Review S09 (tests) | — |
| S11 | code-review-final-impl | Global cross-agent review | — |
| S12 | qv-gate (lint) | `make lint` | — |
| S13 | qv-gate (format) | `make format-check` | — |
| S14 | qv-gate (typecheck) | `make type-check` | — |
| S15 | qv-gate (unit-tests) | `make test-unit` | — |
| S16 | qv-gate (integration-tests) | `make test-integration` (timeout 900) | — |

Agent slugs: `database-impl`, `backend-impl`, `frontend-impl`, `template-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`. (This feature also INTRODUCES a new canonical slug `self-assess-impl` for downstream use, but does not place it on its own manifest — F-00078 is itself unaffected by the new step.)

### Database Changes

- **New tables**: None
- **Modified tables**: PostgreSQL `step_type` enum gets one new value: `self_assess`
- **Migration notes**: Use `ALTER TYPE step_type ADD VALUE 'self_assess'`. Standard pattern in this repo (see existing `step_type` migrations). The migration file is generated by an agent and applied by the daemon; agents must NOT run alembic upgrade.

### API Changes

- **New endpoints**: None.
- **Modified endpoints**: None directly. The Execution Report fragment (`/project/{id}/item/{id}/tab/execution-report`) gains a new section conditionally, but the route signature is unchanged.

### Frontend Changes

- **New components**: None (no React; this is server-rendered Jinja2 + htmx).
- **Modified components**: `dashboard/templates/fragments/item_execution_report.html` — appends a "Self-Assessment" section that renders when `execution_report.self_assessment` is populated. Includes severity-coloured findings grouped by `target` (`iw-ai-core` vs project), a narrative block, and per-finding "Copy paste prompt" buttons (small inline JS using `navigator.clipboard.writeText`).

## File Manifest

All files for this work item live under `ai-dev/active/F-00078/`.

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00078/F-00078_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00078/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/F-00078/prompts/F-00078_S01_Database_prompt.md` | Prompt | S01 |
| `ai-dev/active/F-00078/prompts/F-00078_S02_CodeReview_Database_prompt.md` | Prompt | S02 |
| `ai-dev/active/F-00078/prompts/F-00078_S03_Backend_prompt.md` | Prompt | S03 |
| `ai-dev/active/F-00078/prompts/F-00078_S04_CodeReview_Backend_prompt.md` | Prompt | S04 |
| `ai-dev/active/F-00078/prompts/F-00078_S05_Frontend_prompt.md` | Prompt | S05 |
| `ai-dev/active/F-00078/prompts/F-00078_S06_CodeReview_Frontend_prompt.md` | Prompt | S06 |
| `ai-dev/active/F-00078/prompts/F-00078_S07_Template_prompt.md` | Prompt | S07 |
| `ai-dev/active/F-00078/prompts/F-00078_S08_CodeReview_Template_prompt.md` | Prompt | S08 |
| `ai-dev/active/F-00078/prompts/F-00078_S09_Tests_prompt.md` | Prompt | S09 |
| `ai-dev/active/F-00078/prompts/F-00078_S10_CodeReview_Tests_prompt.md` | Prompt | S10 |
| `ai-dev/active/F-00078/prompts/F-00078_S11_CodeReview_Final_prompt.md` | Prompt | S11 |

QV-gate steps S12..S16 use the `gate` + `command` shape in the manifest (not a `prompt` field) — no per-step prompt file is needed; the executor invokes the declared command directly.

Files this feature will touch in iw-ai-core (not exhaustive — agents add the precise file list in their reports):

| Path | Step | Reason |
|------|------|--------|
| `orch/db/models.py` | S01 | Extend `StepType` enum |
| `orch/db/migrations/versions/<new>.py` | S01 | New Alembic migration adding `self_assess` to the PostgreSQL enum |
| `orch/daemon/project_registry.py` | S03 | Read `self_assess` from `projects.toml`, populate `ProjectConfig.self_assess_enabled` |
| `orch/self_assess.py` | S03 | New helper module |
| `orch/daemon/state_machine.py` or batch_manager.py | S03 | Soft-step semantics for `self_assess` (failure → completed for batch progression) |
| `orch/cli/step_commands.py` | S03 | New `--analysis-json` flag on `iw step-done` |
| `orch/cli/item_commands.py` | S03 | Add `("self-assess", StepType.self_assess)` to `_AGENT_STEP_TYPE_PATTERNS` for register-time inference defense-in-depth |
| `executor/step_executor_lib.sh` | S03 | Register `self-assess-impl` slug (`get_step_type` → `implementation`; `get_agent_label` → `SelfAssess`) |
| `executor/step_executor.sh` | S03 | Export `IW_ITEM_ID` env var to the agent process if not already set |
| `skills/iw-workflow/SKILL.md` | S07 | Extend canonical agent-mapping table with `SelfAssess` / `self-assess-impl` row |
| `.claude/skills/iw-workflow/SKILL.md` | S07 | Synced copy |
| `orch/daemon/execution_report.py` | S05 | Add `self_assessment` field to `ExecutionReportData`; load findings JSON when present |
| `dashboard/templates/fragments/item_execution_report.html` | S05 | Append Self-Assessment section |
| `dashboard/static/styles.css` | S05 | If new Tailwind classes are added, run `make css` (committed) |
| `skills/iw-item-analyze/SKILL.md` | S07 | OpenCode migration + new output contract |
| `skills/iw-new-feature/SKILL.md` | S07 | Inject self_assess step when project flag is on |
| `skills/iw-new-cr/SKILL.md` | S07 | Inject self_assess step when project flag is on |
| `skills/iw-new-incident/SKILL.md` | S07 | Inject self_assess step when project flag is on |
| `templates/design/SelfAssess_Prompt_Template.md` | S07 | New prompt template |
| `.claude/skills/iw-item-analyze/SKILL.md` | S07 | Synced copy |
| `.claude/skills/iw-new-feature/SKILL.md` | S07 | Synced copy |
| `.claude/skills/iw-new-cr/SKILL.md` | S07 | Synced copy |
| `.claude/skills/iw-new-incident/SKILL.md` | S07 | Synced copy |
| `ai-dev/templates/SelfAssess_Prompt_Template.md` | S07 | Synced copy |
| `tests/unit/test_self_assess_parser.py` | S09 | New unit tests |
| `tests/integration/test_self_assess_flow.py` | S09 | New integration tests |
| `tests/integration/test_project_registry_self_assess.py` | S09 | New integration tests |
| `tests/dashboard/test_execution_report_self_assess.py` | S09 | New dashboard render tests |
| `projects.toml` | S03 (test fixture only) or S07 (docs only) | Reference example for the new flag — DO NOT toggle it on by default |

## Acceptance Criteria

### AC1: Project flag is read from projects.toml

```
Given a `[projects.demo]` block in `projects.toml` with `self_assess = true`
When `ProjectRegistry.load()` runs
Then `registry.projects["demo"].self_assess_enabled` is `True`
And when the flag is absent, the field defaults to `False`
```

### AC2: Design skills inject the self_assess step when the project flag is on

```
Given a project where `projects.toml` has `self_assess = true`
When `/iw-new-feature`, `/iw-new-cr`, or `/iw-new-incident` generates a manifest for that project
Then the resulting `workflow-manifest.json` contains exactly one step with
   `agent: "self-assess-impl"` and `step_type: "self_assess"`, placed immediately
   before the first `qv-gate` step (and before any `qv-browser` step)
And when the flag is `false` or absent, no self_assess step is added
And the canonical agent table in `skills/iw-workflow/SKILL.md` lists
   `self-assess-impl` so the orchestrator does not reject the new slug
```

### AC3: Daemon treats self_assess failure as soft (item still merges)

```
Given a work item whose `self_assess` step exits with a non-zero code
When the daemon evaluates batch_item progression
Then the batch_item proceeds to `merging` and ultimately `merged`
And the `WorkflowStep.status` for the self_assess step records `failed` (truth in reporting)
And the failure does NOT trigger a fix cycle, retry, or escalation
```

### AC4: Execution Report shows Self-Assessment section when findings exist

```
Given a work item whose `self_assess` step ran and produced
  `<ID>_self_assess_report.md` and `<ID>_self_assess_findings.json`
When a user opens the Execution Report tab for that item
Then a "Self-Assessment" section appears below the existing Retry Timeline
And the section renders findings grouped by `target` (iw-ai-core vs project)
And each finding shows severity, class, recommendation, and a "Copy paste prompt" button
And the narrative paragraph from the report MD is shown
```

### AC5: Execution Report hides Self-Assessment section cleanly when not applicable

```
Given a work item whose project does NOT have `self_assess: true` (or whose self_assess step did not run)
When a user opens the Execution Report tab
Then NO "Self-Assessment" section appears anywhere on the page
And no placeholder text such as "no analysis available" is shown
```

### AC6: Skill writes both report MD and structured findings JSON

```
Given the migrated `iw-item-analyze` skill is invoked with IW_ITEM_ID set
When the skill completes successfully
Then `<reports_dir>/<ID>_self_assess_report.md` exists with the human-readable narrative
And `<reports_dir>/<ID>_self_assess_findings.json` exists with a JSON array of finding objects
And each finding object contains `severity`, `class`, `target`, `recommendation`, `paste_prompt`
And the file also contains a top-level `coverage_notes` string declaring which logs were sampled vs read fully
```

### AC7: step-done accepts --analysis-json (sidecar convention; no new column)

```
Given a self_assess step run with both report MD and findings JSON files written
When the agent calls `iw step-done <ID> --step S<NN> --report <path.md> --analysis-json <path.json>`
Then the StepRun.report_file column records the report MD path (existing column, no schema change)
And the JSON sidecar path is NOT persisted as a separate column — it is discovered at
   render time via the canonical sidecar convention `<report_stem>_findings.json`
   (implemented as `orch.self_assess.findings_path_for(report_path)`)
And the `--analysis-json` flag enforces three things at CLI time:
   (1) the step's step_type is `self_assess` (else click.UsageError),
   (2) the JSON path lives in the same parent directory as `--report`,
   (3) the path matches the sidecar convention (defensive, prevents drift)
And `assemble_execution_report` can later locate the findings JSON purely from
   `StepRun.report_file` via the convention helper
```

> **Note on persistence choice.** This deliberately avoids a schema change. The
> `--analysis-json` flag is accepted for explicitness and forward-compatibility
> (in case a future change adds a column), but today it is a no-op aside from
> the validation above. See the "Notes" section for the full rationale.

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Project flag absent in projects.toml | `[projects.demo]` has no `self_assess` key | `ProjectConfig.self_assess_enabled = False`; skills do NOT inject the step |
| Project flag set to non-bool (e.g., string "true") | `self_assess = "true"` in projects.toml | Treat as truthy via Python's standard bool coercion ONLY if explicitly true; otherwise log a warning and default to False (matches the staleness config "log and continue" pattern) |
| self_assess step skipped | Step exists but `WorkflowStep.status = skipped` | Execution Report does NOT render Self-Assessment section |
| Findings JSON missing on disk | step.status=completed but file not found | Render an empty section with a single italic line "Self-assessment ran but no findings were captured." (no copy buttons) |
| Findings JSON malformed | File exists but JSON parse fails | Render the narrative MD if available, plus a small italic warning "Findings JSON could not be parsed."; never raise/500 |
| All findings have `target: iw-ai-core` | No project-targeted findings | Render only the "Suggestions for iw-ai-core" subsection |
| All findings have `target: project` | No iw-ai-core-targeted findings | Render only the "Suggestions for {project}" subsection |
| self_assess step fails with non-zero exit | StepRun status=failed | Item still merges (soft step); section shows whatever output was captured (likely partial); section header includes a small "(self_assess failed)" badge for human signal |
| Project flag toggled mid-flight | Flag changes after item is registered but before run | The manifest is the source of truth at register time — already-registered items don't gain or lose the step retroactively |
| Migration applied but no projects opted in | Schema has new enum value but no projects use it | No-op; existing items continue to run unchanged |

## Invariants

1. The `self_assess` step never blocks merge — regardless of exit code, batch_item progression continues to `merging`.
2. The Self-Assessment section in the Execution Report tab is invisible (zero DOM nodes) when the project's `self_assess_enabled` is false OR the step did not run.
3. The findings JSON file path is canonical: `ai-dev/work/<ID>/reports/<ID>_self_assess_findings.json` (and the report MD is the same path with `_report.md` suffix).
4. `iw-item-analyze` (post-migration) NEVER edits files outside `ai-dev/work/<ID>/reports/` — only writes the two output files; remains read-only with respect to the rest of the worktree.
5. The `target` field on every finding is one of exactly two strings: `"iw-ai-core"` or `"project"`. Other values are rejected by the parser.
6. Design-skill manifest generation is deterministic for a given project flag state — no random ordering of injected steps.
7. When the orch DB enum is extended, the migration is forward-only; rolling back the migration without first removing all rows referencing `self_assess` would fail (standard PostgreSQL enum behavior — accept this).

## Dependencies

- **Depends on**: None (the existing `iw-item-analyze` skill, `StepType` enum machinery, `projects.toml` registry, and execution_report renderer all exist).
- **Blocks**: None directly. Future "iw item-digest" CLI helper would build on this if oversized logs prove a problem.

## TDD Approach

- **Unit tests**:
  - `orch/self_assess.py` findings JSON parser: valid input, missing fields, malformed JSON, unknown `target` value, oversized file, empty findings list.
  - `ProjectConfig` builder: presence/absence of `self_assess` flag, non-bool values, mixed casing.
  - Soft-step normalization helper: `failed` self_assess + non-self_assess `failed` should differ.
- **Integration tests**:
  - `projects.toml` round-trip via `ProjectRegistry.load()` with the flag on/off.
  - End-to-end daemon flow with a mocked self_assess step that fails — assert batch_item still reaches `merged`.
  - `assemble_execution_report` loads findings when the JSON sidecar exists; omits the field when absent.
  - Dashboard fragment render via `TestClient`: with/without findings, with all-iw-ai-core / all-project / mixed targets.
  - Design-skill simulation (or unit test that loads the SKILL.md and asserts the conditional injection contract is documented and a sample run produces the expected manifest delta).
- **Edge cases**:
  - Findings JSON exists but step status is `skipped` — section should NOT render.
  - Project has flag on but no step ran (e.g., item registered before flag flip) — section should NOT render.
  - Multiple runs of the self_assess step (retry was attempted somehow) — section uses the latest run's findings.
  - Very large findings JSON (>100 KB) — render but truncate per-finding evidence quotes to a sane length.

## Notes

- **Manifest generation**: The design skills (`iw-new-feature`, `iw-new-cr`, `iw-new-incident`) currently run on the user's machine where `projects.toml` is directly readable. The conditional step injection logic should live in the skill body (not in the iw CLI), keeping the iw CLI free of skill-specific concerns. The skill reads `projects.toml`, looks up the current project's `self_assess` value, and decides whether to add the step.
- **Why `projects.toml` instead of `.iw-orch.json` for the flag** — `browser_verification` and `scope_gate_enabled` live in `.iw-orch.json` because they are *runtime* configuration consumed by the daemon at step launch time (port pools, env scripts, gate toggles applied to specific commits). `self_assess` is a different beast: it is a *project-membership* decision — "this project participates in the post-execution analysis program" — analogous to whether the project is `enabled` at all, or which `services` it declares for staleness tracking. Both of those membership/enrollment fields already live in `projects.toml`. Putting `self_assess` next to them keeps the registry as the single source of truth for "which projects opt into which platform programs" and avoids splitting a single conceptual decision across two files. Runtime configuration (e.g., custom timeout, custom skill path) — if it ever appears — would belong in `.iw-orch.json` next to `browser_verification`.
- **New agent slug `self-assess-impl`** — runs through the standard `step_executor.sh` path (no custom lifecycle), launched as an LLM agent (opencode/claude-code) with the `iw-item-analyze` skill available. Registration touches three places: `executor/step_executor_lib.sh` (S03), `skills/iw-workflow/SKILL.md` canonical agent table (S07), and the `iw-item-analyze` SKILL.md frontmatter (S07, OpenCode-compatible).
- **Soft-step implementation note**: Two viable code points — (a) at `iw step-done` / `iw step-fail` time, the CLI checks `step_type == self_assess` and forces status=completed regardless of the agent's claim; (b) at batch_item progression in `batch_manager`, treat self_assess `failed` as terminal-success. Option (b) preserves truth in the StepRun record (the dashboard can show the actual run failure) while still letting the merge proceed. Prefer (b).
- **`iw step-done --analysis-json` flag**: persist on the StepRun row. If a new column is preferred over reusing `report_file`, the migration must add it. To keep schema churn minimal, the simplest implementation reuses `report_file` for the markdown narrative path and uses a sidecar discovery convention: the parser tries `<report_path_minus_extension>_findings.json` automatically. This avoids a schema change and is the path of least resistance — DOCUMENT this convention in `orch/self_assess.py` so future readers don't grep for a column that does not exist.
- **Skill master copy + sync**: Master is `skills/iw-item-analyze/SKILL.md`. `iw skills sync` copies it to project worktrees. Since `OpenCode` reads `.claude/skills/` paths, keeping the master at `.claude/skills/iw-item-analyze/SKILL.md` after the migration would also work — but the existing repo convention puts masters in `skills/` and syncs from there. Stay consistent with the existing pattern; the OpenCode skill format (no `allowed-tools`, no `argument-hint`, no `$ARGUMENTS`) is achievable in the same `skills/` location.
- **`$IW_ITEM_ID` env var**: The executor scripts already export item context to step processes (see `executor/` and `orch/daemon/worktree_compose.py` for similar env injection patterns). If `IW_ITEM_ID` is not currently exported, S03 must add it to the step launch envelope. Verify in the executor's launch script.
- **Risk: large logs** — `iw-item-analyze` was designed for human chat output. Migrating to file output is straightforward, but the agent must be told to use selective reads on multi-MB log files. This is enforced in the SKILL.md body (no infrastructure-side limit). The `coverage_notes` field gives the human reader honest signal about what was sampled vs read fully.
- **Cost note** — every opted-in item will spend an extra LLM step (~2-5 minutes typical) before merge. The user explicitly opted out of any cost gate; default-off keeps the blast radius narrow until projects deliberately enable it.
- **Master copy location for OpenCode**: confirmed in `docs/misc/guide_to_create_opencode_skills.md` — OpenCode reads `.claude/skills/` paths automatically, and the migration checklist lists the CC-only fields to strip. Keep `skills/` as the master location for cross-project sync; the format change is purely about the file content.
