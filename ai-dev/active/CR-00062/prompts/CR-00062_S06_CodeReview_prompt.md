# CR-00062_S06_CodeReview_prompt

**Work Item**: CR-00062 — Add Pi (pi.dev) as a third agent runtime
**Step Being Reviewed**: S01 (database-impl), S03 (pipeline-impl), S04 (backend-impl), S05 (tests-impl)
**Review Step**: S06
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Read-only `docker ps / inspect / logs` allowed. No state-changing commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You are reviewing — do NOT run any alembic command.

## Input Files

- Design doc: `ai-dev/active/CR-00062/CR-00062_CR_Design.md`
- Step reports:
  - `ai-dev/active/CR-00062/reports/CR-00062_S01_Database_report.md`
  - `ai-dev/active/CR-00062/reports/CR-00062_S03_Pipeline_report.md`
  - `ai-dev/active/CR-00062/reports/CR-00062_S04_Backend_report.md`
  - `ai-dev/active/CR-00062/reports/CR-00062_S05_Tests_report.md`
- The git diff of S01..S05 (use `git diff main...HEAD -- <impacted_paths>`)
- Project conventions: `CLAUDE.md`, `orch/CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00062/reports/CR-00062_S06_CodeReview_report.md`

## Context

You are performing a per-agent code review covering S01 (migration + model comments), S03 (eight dispatch sites + allowlist), S04 (agents/pi/ tree + sync engine), and S05 (tests). Findings are filed with severities; S07 (`code-review-fix-impl`) will apply CRITICAL and HIGH findings.

## Requirements

### Review checklist — S01 (database-impl)

- [ ] Revision file matches `d1e2f3gpt53c` pattern (SERIAL sequence realignment + ON CONFLICT idempotency).
- [ ] Both rows have `enabled=true`, `is_default=false`, `sort_order` 25 and 26.
- [ ] `display_name` strings exactly match the design: "Pi + MiniMax 2.7" and "Pi + GPT-5.3 Codex".
- [ ] `downgrade()` is symmetric and explicit (one DELETE per row, not a blanket `WHERE cli_tool='pi'`).
- [ ] Column-comment updates: `StepRun.cli_tool` and `Batch.cli_tool` both say `"LLM CLI tool used: 'opencode', 'claude', or 'pi'"`.
- [ ] `Batch.cli_tool` `server_default='opencode'` unchanged.
- [ ] No CHECK constraint added (design-time decision; allowlist is code-only).
- [ ] `make migration-check` was run locally and reported green (verify by S01 report's preflight section).

### Review checklist — S03 (pipeline-impl)

For each of the eight dispatch sites, verify the `pi` branch:

- [ ] `executor/step_executor.sh:130` — `pi -p "$INSTRUCTION" --model "$MODEL"`; `setsid timeout` wrapper present; error message in the `else` branch updated to mention pi.
- [ ] `executor/step_executor_lib.sh:616` — new `pi)` case pipes stdin into `pi -p --model "$model"`.
- [ ] `orch/daemon/batch_manager.py:1466` — `pi -p "$(cat {prompt_file})" --model {resolved_model}`.
- [ ] `orch/daemon/fix_cycle.py:2206-2230` `_build_fix_launch_argv()` — no logic change; new comment line explaining pi/claude fall through to `/bin/sh -c`.
- [ ] `orch/daemon/fix_cycle.py:2286` — pi inner command shape.
- [ ] `orch/daemon/doc_job_poller.py:298` — pi arm + explicit `else: raise ValueError`.
- [ ] `orch/doc_service.py:573` — pi arm + explicit `else: raise ValueError`.
- [ ] `orch/daemon/project_registry.py:155` — `_VALID_CLI_TOOLS = {"opencode","claude","pi"}` module-level constant; warn-and-skip on unknown values.

Also verify:
- [ ] No PTY wrapper used for pi (this is opencode-only — verify by reading `_build_fix_launch_argv`).
- [ ] No `--dangerously-skip-permissions` or `--permission-mode bypassPermissions` flag on the pi command (Pi uses extensions for permissions per R-00072 §7).

### Review checklist — S04 (backend-impl)

- [ ] `agents/pi/` directory exists and contains the same set of .md filenames as `agents/claude/` (count match).
- [ ] Any stubbed agent files carry a `TODO(CR-00062-followup):` comment naming the slug and the porting work.
- [ ] `AgentSyncResult.pi_agents_synced` field added with default 0.
- [ ] `sync_agents_and_commands()` includes a `_sync_directory(... agents/pi, .pi/agents)` call between Claude and OpenCode sync calls.
- [ ] `sync_agents_cmd` JSON output includes `"pi_agents"` key.
- [ ] `sync_agents_cmd` human output prints `Pi agents: N` line and includes pi in the total.
- [ ] `projects.toml` is unchanged (no project was switched to pi per the GO/NO-GO decision).

### Review checklist — S05 (tests-impl)

- [ ] All four test files exist and target the right module surfaces.
- [ ] Test counts: 12+ assertions for argv dispatch; 6+ for sync_agents; 6+ for project_registry allowlist; 10+ for end-to-end integration.
- [ ] Stub `pi` binary fixture is correct (executable bit set, PATH-prepended via monkeypatch, deterministic stdout marker).
- [ ] Catalogue lookup integration test runs against the testcontainer DB seeded by S01's migration (not a mocked session).
- [ ] No `importlib.reload(orch.config)` in any test (must use `monkeypatch.delenv()` per `tests/CLAUDE.md`).
- [ ] No tests mock the DB session in integration tests.
- [ ] FTS DDL hook present where `Base.metadata.create_all()` is invoked in test fixtures.
- [ ] No silent `pytest.skip(...)` — every `skipif` has a documented reason.
- [ ] Tests check both the happy paths AND the negative cases (typo cli_tool raises ValueError, unknown model falls back to default).

### Cross-cutting checks

- [ ] No scope creep — only files in `scope.allowed_paths` were modified.
- [ ] No regression in opencode or claude dispatch (existing tests should still pass; targeted re-run of `tests/unit/test_*opencode*.py` if any).
- [ ] All four implementation steps' preflight gates ran clean (`make format`, `make typecheck`, `make lint` per report).

## Project Conventions

`CLAUDE.md`, `orch/CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`. Treat any deviation from project conventions as a HIGH finding at minimum.

## TDD Verification

Verify each implementation step's `tdd_red_evidence` field is populated correctly:
- S01: should be `"n/a — data-only migration ..."`
- S03: should name at least one site with captured RED→GREEN failure line.
- S04: should name `AttributeError ... pi_agents_synced` RED line.
- S05: should record RED evidence or the explicit n/a note per the prompt.

Missing or vague `tdd_red_evidence` is a HIGH finding.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00062/reports/CR-00062_S06_CodeReview_report.md"
  ],
  "preflight": {
    "format": "n/a — review only",
    "typecheck": "n/a — review only",
    "lint": "n/a — review only"
  },
  "tests_passed": true,
  "test_summary": "review-only",
  "tdd_red_evidence": "n/a — review step",
  "findings": [
    {"id": "F1", "severity": "CRITICAL|HIGH|MEDIUM|LOW", "step": "S0X", "file": "<path>", "summary": "<one line>"}
  ],
  "blockers": [],
  "notes": ""
}
```

Findings are recorded in the report file; the JSON `findings` array is a summary index.
