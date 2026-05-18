# CR-00062_S08_CodeReview_Final_prompt

**Work Item**: CR-00062 — Add Pi (pi.dev) as a third agent runtime
**Step**: S08
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Read-only `docker ps / inspect / logs` allowed. No state-changing commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You are reviewing — do NOT run any alembic command.

## Input Files

- Design doc: `ai-dev/active/CR-00062/CR-00062_CR_Design.md`
- All prior step reports (S01..S07)
- S07's `findings_addressed` list
- Project conventions across `CLAUDE.md`, `orch/CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`
- Full diff: `git diff main...HEAD`

## Output Files

- `ai-dev/active/CR-00062/reports/CR-00062_S08_CodeReview_Final_report.md`

## Context

This is the cross-agent final review. You are looking for integration-level problems — issues that no single per-agent review (S06) could have caught because they span layer boundaries. Examples for this CR:

- A new `pi` row resolved in `agent_runtime/resolver.py` doesn't actually match what the executor's `step_executor.sh` invokes (model string drift between catalogue and dispatch).
- `project_registry.py`'s allowlist accepts `pi` but `doc_job_poller.py` still raises `ValueError` because S03 missed adding the pi arm there (or vice versa — accepts in registry, missing in one dispatch site).
- Tests in S05 mock something that the integration boundary doesn't tolerate (e.g., a mocked session that hides a real schema mismatch).
- The dashboard runtime-override picker (`dashboard/routers/runtime_overrides.py`) was assumed to be runtime-agnostic at design time; verify by reading it that this assumption held.
- A new agent file in `agents/pi/` references a skill that doesn't exist or names a tool that pi can't invoke.

## Requirements

### 1. Read the full diff end-to-end

`git diff main...HEAD` then `git log main...HEAD --stat`. Build a mental map of which files were touched by which step.

### 2. Cross-cutting integration checks

- [ ] **Model strings match**: every `--model X` argument constructed in any dispatch site corresponds to a real row in `agent_runtime_options` (the two new pi rows + the existing seeded rows). No drift.
- [ ] **Allowlist consistency**: `_VALID_CLI_TOOLS` in `project_registry.py` matches the set of branches in all eight dispatch sites. A future contributor adding `aider` to the allowlist should be visibly forced to update all dispatch sites — make sure the allowlist constant is referenced from at least one dispatch site as a sanity check (or note in S08 report if it isn't, as a follow-up suggestion).
- [ ] **Dashboard endpoint unchanged**: `dashboard/routers/runtime_overrides.py` was NOT modified. Verify by `git diff main...HEAD -- dashboard/`.
- [ ] **Sync-agents counter consistent**: `pi_agents_synced` is computed, returned, printed (human + JSON), and included in the total.
- [ ] **No PTY wrapper for pi**: in `fix_cycle._build_fix_launch_argv`, `cli_tool == "pi"` does NOT go through `script -qec` (only opencode does).
- [ ] **Migration round-trip clean**: S02 reported green; if S07 modified the migration after S02, the migration-check needs to be re-run in S08's environment.
- [ ] **No regressions in claude/opencode**: every existing test that exercises claude or opencode dispatch still passes. Run a targeted subset:
  ```bash
  uv run pytest tests/unit/test_pi_runtime_dispatch.py tests/unit/test_sync_agents_pi.py -v
  ```
- [ ] **Scope compliance**: every modified file falls within `workflow-manifest.json:scope.allowed_paths`. Use `git diff --name-only main...HEAD` and grep against the scope list.

### 3. Re-check the acceptance criteria

Walk AC1..AC6 in the design doc and tick off each one against the diff. Note any AC that lacks unambiguous test evidence.

### 4. R-00072 cross-reference

Read R-00072 §1 and §7 and confirm the implementation aligns with R-00072's findings on Pi's CLI surface (print mode is one-shot stdin→stdout; no `--dangerously-skip-permissions` equivalent; no MCP). If S03 / S04 introduced any flag or assumption that contradicts R-00072, flag it.

### 5. Doc-system / Sibling-repo cross-reference

`agents/pi/` is the master copy. Sibling repos (`iw-doc-plan`, `podforger`, `cv`) will pick it up via their next `iw sync-agents`. Verify the master tree is internally consistent (no broken cross-references between agent files, no agent file references a skill that doesn't exist under `skills/`).

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-final-impl",
  "work_item": "CR-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00062/reports/CR-00062_S08_CodeReview_Final_report.md"
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
    {"id": "FF1", "severity": "CRITICAL|HIGH|MEDIUM|LOW", "summary": "<cross-cutting concern>"}
  ],
  "ac_coverage": {
    "AC1": "satisfied|gap:<note>",
    "AC2": "satisfied|gap:<note>",
    "AC3": "satisfied|gap:<note>",
    "AC4": "satisfied|gap:<note>",
    "AC5": "satisfied|gap:<note>",
    "AC6": "satisfied|gap:<note>"
  },
  "blockers": [],
  "notes": ""
}
```
