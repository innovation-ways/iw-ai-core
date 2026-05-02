# F-00078_S03_Backend_prompt

**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state. See S01 prompt for full list.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live DB.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00078 --json`.
- `ai-dev/active/F-00078/F-00078_Feature_Design.md` -- Design document
- `ai-dev/work/F-00078/reports/F-00078_S01_Database_report.md` -- S01 report
- `orch/daemon/project_registry.py` -- Where the new flag goes
- `orch/daemon/browser_env.py` -- Reference for the opt-in flag pattern (`is_browser_verification_step`)
- `orch/daemon/state_machine.py` -- Step state transitions
- `orch/daemon/batch_manager.py` -- Where batch_item progression happens (search for `BatchItemStatus.merging`, `mark_item_completed`)
- `orch/cli/step_commands.py` -- `iw step-done` / `iw step-fail` CLI; you'll add `--analysis-json`
- `executor/step_executor_lib.sh` -- `get_step_type()` and `get_agent_label()` switches; you'll add a case for `self-assess-impl`
- `executor/step_executor.sh` -- agent process launch; you'll verify (or add) the `IW_ITEM_ID` env var export
- `executor/CLAUDE.md` -- executor-layer rules

## Output Files

- `ai-dev/work/F-00078/reports/F-00078_S03_Backend_report.md` -- Step report
- Modified: `orch/daemon/project_registry.py`, `orch/daemon/batch_manager.py` (or `orch/daemon/state_machine.py`), `orch/cli/step_commands.py`, `executor/step_executor_lib.sh`, `executor/step_executor.sh` (only if `IW_ITEM_ID` was missing)
- Created: `orch/self_assess.py`

## Context

You are implementing the backend layer for **F-00078**. Your job: wire the new `self_assess` step type into the project registry, the daemon's progression logic, and the `iw` CLI — without touching the dashboard, skills, or design templates.

Read the design document first. Pay special attention to:
- "Implementation Plan" → "Database Changes" (already done in S01) and the soft-step semantics description
- "Acceptance Criteria" → AC1, AC3, AC7
- "Boundary Behavior" — every row is a mandatory test case
- "Notes" — especially the soft-step implementation note (option (b): handle at batch_item progression, not at step-done time, to preserve truth on the StepRun row)

## Requirements

### 1. Extend `ProjectConfig` and `_build_project_config`

In `orch/daemon/project_registry.py`:

- Add a new field to the `ProjectConfig` dataclass:
  ```python
  self_assess_enabled: bool = False
  ```
- In `_build_project_config(project_id, entry)`, read `self_assess` from the `entry` dict:
  ```python
  self_assess_enabled: bool = bool(entry.get("self_assess", False))
  ```
  Note: `entry` here is the per-project section of `projects.toml`. If the value is present but not a bool (e.g., a stray string `"true"`), Python's `bool()` coerces non-empty strings to `True` — match the design doc's Boundary Behavior table: explicit `True` is truthy, anything else (including `"true"`, integers, etc.) should default to `False` with a warning. Implement this strictness:

  ```python
  raw = entry.get("self_assess", False)
  if isinstance(raw, bool):
      self_assess_enabled = raw
  else:
      logger.warning(
          "Project %r has non-bool 'self_assess' value %r — defaulting to False",
          project_id, raw,
      )
      self_assess_enabled = False
  ```
- Pass `self_assess_enabled` through to the `ProjectConfig(...)` constructor.
- Do NOT propagate this value to the DB `Project.config` JSONB column unless the existing pattern already does that for similar flags (it does not for the `enabled` field — keep `self_assess_enabled` as in-memory-only, mirroring `scope_gate_enabled`).

Document the new field with a brief inline comment matching the style of the existing `scope_gate_enabled` comment.

### 2. Create `orch/self_assess.py`

A new module with helpers that the daemon and the dashboard's execution_report assembler will both import. Layout:

```python
"""Helpers for the self_assess step type.

The self_assess step runs the iw-item-analyze skill against a just-completed
work item before merge. It is purely informational — failures never block
merge (see is_soft_step). The skill's structured findings are written to disk
as <ID>_self_assess_findings.json alongside the human-readable
<ID>_self_assess_report.md narrative; both files live in the per-item
reports dir.

This module provides:
  - SelfAssessFinding / SelfAssessmentData dataclasses
  - parse_findings_json: tolerant JSON parser
  - is_self_assess_step: type-narrowing helper
  - findings_path_for: convention-based sidecar path resolver
  - is_soft_step_failure: should this step's failure block batch progression?
"""
```

Required public symbols:

- `SelfAssessFinding` (frozen dataclass): `severity: Literal["HIGH", "MED", "LOW"]`, `clazz: str` (avoid the keyword `class`), `target: Literal["iw-ai-core", "project"]`, `title: str`, `recommendation: str`, `paste_prompt: str`, `evidence: list[str]` (default empty), `effort: str | None` (default None).
- `SelfAssessmentData` (frozen dataclass): `narrative_md: str | None`, `findings: list[SelfAssessFinding]`, `coverage_notes: str | None`, `bottom_line: str | None`.
- `parse_findings_json(text: str) -> SelfAssessmentData` — tolerant: unknown fields ignored; required fields missing → `SelfAssessParseError`; invalid `target` value → `SelfAssessParseError`.
- `class SelfAssessParseError(ValueError)`.
- `is_self_assess_step(step_type) -> bool` — accepts a `StepType` enum or string, returns True only for `self_assess`. Mirror the existing `browser_env.is_browser_verification_step` shape.
- `findings_path_for(report_path: Path | str) -> Path` — convention: replace the trailing `_report.md` (or just `.md`) with `_findings.json`. The dashboard uses this to discover the sidecar from the `StepRun.report_file` value.
- `is_soft_step_failure(step_type, run_status) -> bool` — returns True when step_type is `self_assess` AND run_status is a failure (failed/timeout/killed/stalled). Used by batch progression.

### 3. Soft-step semantics in batch progression

Open `orch/daemon/batch_manager.py` and locate the place where it decides whether all steps are done before flipping the batch_item to `merging`. Add a soft-step rule:

- When deciding whether a step "blocks" completion: if the step's `step_type == StepType.self_assess` AND its final status is `failed`, treat it as `completed` for the purposes of batch_item progression.
- Do NOT mutate the StepRun row's actual status — the report must show the truth.
- Do NOT trigger a fix cycle for self_assess failures (no `FixCycle` row should be created). The fix-cycle launcher must skip self_assess.

Cross-check `orch/daemon/fix_cycle.py` and `orch/daemon/step_monitor.py` for any place that branches on step type for fix-cycle creation; add a guard `is_self_assess_step(step.step_type)` and short-circuit (no fix-cycle, mark as terminal).

### 4. `iw step-done --analysis-json` flag

The existing `step-done` command (in `orch/cli/step_commands.py`, around line 277) currently has this signature:

```
iw step-done <ITEM_ID> --step S<NN> --report <path>
```

i.e., `item_id` is a positional argument, `--step` and `--report` are options. Preserve that shape and add a new optional flag:

```python
@click.option(
    "--analysis-json",
    "analysis_json_path",
    type=click.Path(exists=False, dir_okay=False),
    default=None,
    help="Path to the structured findings JSON (self_assess steps only). "
         "Convention: <report path stem>_findings.json. The dashboard auto-"
         "discovers this sidecar from the report path; this flag is accepted "
         "for explicit clarity but is not required.",
)
```

Resulting invocation: `iw step-done <ID> --step S<NN> --report <path.md> --analysis-json <path.json>`.

Behavior:
- If `--analysis-json` is provided AND the resolved step's `step_type` is NOT `self_assess`, raise a `click.UsageError`.
- If provided, validate the path resolves to the same parent directory as `--report` (defensive — prevents the agent from writing the JSON to a random place).
- If provided AND `--report` is not provided, raise `click.UsageError` (sidecar without a report has no canonical anchor).
- The path itself is NOT persisted in a new column — discovery uses `findings_path_for(report_path)`. The flag exists for explicitness and for future use if we later add a column.

Update the corresponding `step-fail` similarly: a `self_assess` step that calls `step-fail` should still allow `--analysis-json` (the agent might have produced partial findings before failing).

### 5. Document where the executor exports `IW_ITEM_ID`

If the executor's step launcher does not already export `IW_ITEM_ID` to the agent process environment, add it. Search `executor/` and `orch/daemon/` for the env-var injection pattern (similar to `IW_BROWSER_BASE_URL`, `IW_STEP_ID`). The skill's body relies on this env var as a replacement for Claude Code's `$ARGUMENTS`. If it's already set, leave it alone and note in your report that you verified it.

### 6. Register the new agent slug in `executor/step_executor_lib.sh`

Open `executor/step_executor_lib.sh`. Two switch statements need a new case so the executor recognises the slug:

**`get_step_type()`** — locate the `case "$agent" in` block (around line 111). Add a case ABOVE the catch-all `*) echo "implementation"` line:

```bash
self-assess-impl|self_assess_impl)
    echo "implementation" ;;
```

The `self-assess-impl` agent runs through the standard implementation launcher (`step_executor.sh`'s LLM-agent path) — same as `database-impl`, `backend-impl`, etc. Do NOT route it through the `browser` lifecycle (that has custom env_up/env_down hooks). Returning `"implementation"` gives the right timeout (`MAX_STEP_TIMEOUT_IMPL`) and the standard launch behavior. The soft-step semantics live in the daemon (Section 3 above), not here — the executor stays generic.

**`get_agent_label()`** — locate the function (around line 136). Add a case BEFORE the catch-all `*) echo "$agent"`:

```bash
self-assess-impl)             echo "SelfAssess" ;;
```

This makes report filenames like `F-00099_S11_SelfAssess_report.md` consistent with the existing `Frontend`, `Backend`, `Database`, `Tests`, `Template` labels.

Do NOT modify `get_step_timeout()` — `implementation` already has a sensible timeout. Do NOT modify `get_fix_agent_for_review()` — there is no fix agent for `self-assess-impl` because the soft-step semantics short-circuit fix cycles entirely (see Section 3).

### 6c. Defense-in-depth: register-time step_type inference

`orch/cli/item_commands.py` defines `_AGENT_STEP_TYPE_PATTERNS` (around line 76) and `agent_to_step_type()`. The register flow honors an explicit `"step_type"` field on each manifest step (line ~396) and falls back to slug-pattern inference when it is absent. The design skills (S07) DO inject `"step_type": "self_assess"` explicitly, so the happy path works without changes here.

To prevent silent failure if anyone hand-writes or re-emits a manifest WITHOUT the explicit field, ALSO append a pattern entry so the slug `self-assess-impl` infers correctly:

```python
_AGENT_STEP_TYPE_PATTERNS: list[tuple[str, StepType]] = [
    ("code-review-fix-final", StepType.code_review_fix_final),
    ...
    ("self-assess", StepType.self_assess),  # NEW — matches self-assess-impl, self-assess
    ...
]
```

Place it before the catch-all so any slug starting with `self-assess` resolves to `StepType.self_assess`. Add `orch/cli/item_commands.py` to your `files_changed`.

### 7. Do NOT touch

- `dashboard/` (S05's job)
- `skills/` (S07's job)
- `templates/design/` (S07's job)
- `tests/` test additions for full coverage (S09's job — but you MUST add minimal happy-path tests for your new code; see TDD section)

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `dashboard/CLAUDE.md` for:

- SQLAlchemy 2.0 sync style
- The "Critical Rules" list (no docker compose up; no live-DB alembic)
- Click 8.1 CLI patterns in `orch/cli/`
- The `browser_verification` precedent — your soft-step plumbing should feel like a sibling of that pattern

## TDD Requirement

RED before GREEN:

1. **RED**: Write tests for each new helper in `orch/self_assess.py` (in `tests/unit/test_self_assess.py`):
   - `parse_findings_json` happy path with a complete fixture string
   - `parse_findings_json` rejects unknown `target` value
   - `is_soft_step_failure` returns True for `self_assess + failed`, False for `self_assess + completed`, False for `implementation + failed`
   - `findings_path_for` correctly derives the sidecar path
2. **GREEN**: implement the helpers.
3. **REFACTOR**: tighten and pass.

For the daemon-side soft-step logic, write a focused integration test (or extend an existing batch_manager test) asserting that a self_assess step with `failed` status does NOT block transition to `merging`. Place it in `tests/integration/` — but if comprehensive integration coverage feels like S09 territory, write only the minimum here and let S09 expand.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fix formatting drift; inspect diff and re-stage.
2. `make typecheck` — zero errors in your touched files.
3. `make lint` — zero errors.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` — must pass (your new self_assess unit tests included).
2. `make test-integration` — must pass.
3. `make lint` and `make type-check` — zero errors.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/project_registry.py",
    "orch/self_assess.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py",
    "orch/cli/step_commands.py",
    "orch/cli/item_commands.py",
    "executor/step_executor_lib.sh",
    "executor/step_executor.sh",
    "tests/unit/test_self_assess.py",
    "tests/integration/test_batch_manager_self_assess.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Document whether IW_ITEM_ID was already exported by the executor or whether you added it; document the exact files where soft-step branching landed."
}
```
