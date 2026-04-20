# F-00056_S03_Backend_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step**: S03
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- Design document (read Scope, File Manifest, AC1, AC3, AC4, AC5, AC6, AC9, Boundary Behavior, Invariants)
- `ai-dev/active/F-00056/reports/F-00056_S02_CodeReview_report.md` -- S02 review verdict
- `orch/db/models.py` -- `WorkflowStep`, `StepRun`, `FixCycle`, `WorkItem` models (now including `FixCycle.fix_summary` from S01)
- `orch/daemon/batch_manager.py:626-658` -- `_complete_item()` (hook location for auto-generation)
- `orch/daemon/fix_cycle.py` -- fix-cycle lifecycle (where fix-summary parsing goes)
- `orch/cli/item_commands.py:460-576` -- CLI pattern to mirror for `iw item-report`
- `orch/cli/main.py` -- CLI entry point
- `orch/archive/archiver.py:26-100` -- archive dir resolution (used to decide report file path)
- `ai-dev/templates/CodeReview_FIX_Prompt_Template.md` -- fix prompt template to edit
- `ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md` -- fix prompt template to edit
- `ai-dev/templates/QualityValidation_FIX_Prompt_Template.md` -- fix prompt template to edit

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S03_Backend_report.md` -- Step report

## Context

You are building the backend for the Work Item Execution Report feature. No schema changes in this step (S01 handled those). You assemble report data from the DB, render it to markdown, expose a CLI, auto-trigger generation at item-completion, ingest the fix agent's `fix_summary` into the DB, and update the three fix prompt templates to require `fix_summary` in the result contract.

The design document is normative. Every deliverable below maps to a specific AC or Invariant; when in doubt, re-read those sections.

## Requirements

### 1. Report assembly service: `orch/daemon/execution_report.py` (new file)

Create a new module with these public entries:

- `@dataclass(frozen=True) class StepRunSegment:` — one StepRun row, shaped for the Gantt/timeline. Fields: `run_number`, `status`, `started_at`, `completed_at`, `duration_secs`, `error_message`, `report_file`, `report_content` (optional inline), `is_final_attempt` (bool), `gantt_class` (one of `"completed"`, `"failed"`, `"retry"`, `"in_progress"`, `"skipped"`), `left_pct` (float, precomputed from `(started_at - item_start) / total_duration * 100`, clamped to `[0.0, 100.0]`), `width_pct` (float, precomputed from `(completed_at - started_at) / total_duration * 100`, clamped to min `0.5` and max so that `left_pct + width_pct <= 100.0`; for `completed_at is None`, computed from `now - started_at`).
- `@dataclass(frozen=True) class FixCycleEntry:` — one FixCycle row. Fields: `cycle_number`, `trigger_type`, `trigger_report`, `fix_report`, `fix_summary`, `status`, `started_at`, `completed_at`, `duration_secs`, `left_pct` (float, precomputed fix-marker left offset between its bounding retry segments, same mapping as `StepRunSegment.left_pct`), `width_pct` (float, precomputed fix-marker width; same clamping rules).
- `@dataclass(frozen=True) class StepRow:` — one WorkflowStep + its runs + its fix cycles. Fields: `step_id` (e.g., "S13"), `step_number`, `step_type`, `step_label`, `agent_label`, `opencode_agent`, `display_label` (derived per fallback rules), `runs: list[StepRunSegment]`, `fix_cycles: list[FixCycleEntry]`, `max_run_number`, `final_status`, `is_hotspot` (bool, `max_run_number >= 2`), `total_duration_secs`.
- `@dataclass(frozen=True) class RetryHotspot:` — Fields: `step_id`, `display_label`, `retry_count` (= `max_run_number`), `final_status`.
- `@dataclass(frozen=True) class ExecutionReportData:` — top-level. Fields: `project_id`, `work_item_id`, `work_item_title`, `work_item_type`, `work_item_status`, `verdict` (one of `"completed"`, `"failed"`, `"stalled"`, `"in_progress"`, `"not_started"`), `verdict_badge` (e.g., `"✓ Completed"`), `item_started_at`, `item_completed_at`, `total_duration_secs`, `steps: list[StepRow]`, `hotspots: list[RetryHotspot]` (sorted retry_count desc, then step_number asc), `generated_at`.

Provide one public function:

```python
def assemble_execution_report(
    session: Session, project_id: str, work_item_id: str
) -> ExecutionReportData: ...
```

Implementation rules:

- Use a single transaction; fetch `WorkItem`, `WorkflowStep`, `StepRun`, `FixCycle` scoped by `project_id` + `work_item_id` (Invariant 12: per-project isolation).
- `display_label` fallback order: `step_label` → `agent_label` → `opencode_agent` → `step_id`.
- Gantt percentages (`left_pct`, `width_pct`) are computed inside `assemble_execution_report` so the template does no arithmetic. Use the item's `total_duration_secs` as the denominator. When `total_duration_secs == 0` (zero-StepRun item), set both to `0.0`. Round to 2 decimal places in storage. Enforce Invariant 2 (per-row sum ≤ 100%, min segment 0.5%) in the assembly layer — the template should receive numbers it can emit verbatim.
- `gantt_class` assignment rule (Invariant 1, 2, 3, and design Gantt spec):
  - If `run_number < max_run_number` for that step → `"retry"` regardless of individual `status`.
  - Else if `status == StepStatus.completed` (or `RunStatus.completed`) → `"completed"`.
  - Else if `status == StepStatus.failed` (or `RunStatus.failed`) → `"failed"`.
  - Else if `completed_at is None` → `"in_progress"`.
  - Else if `status == StepStatus.skipped` → `"skipped"`.
- `total_duration_secs` on an item: `max(completed_at for all runs) - min(started_at for all runs)`; if in-progress, use `datetime.now(tz=UTC)` for the end; if no runs at all, return 0.
- `hotspots` list contains only `StepRow` where `is_hotspot` is True, sorted by `retry_count` desc then `step_number` asc (AC6).
- `verdict`: map from `WorkItem.status` to the five strings above; "not_started" when no StepRun rows exist.

Do NOT cache anything; this is an idempotent synchronous function called on demand.

### 2. Markdown renderer in the same module

```python
def render_execution_report_markdown(data: ExecutionReportData) -> str: ...
```

Produces a single markdown document with four sections, in order:

1. **Header + verdict**
   - `# Execution Report: {work_item_id} — {work_item_title}`
   - blank line
   - bullet list: `**Verdict**: {verdict_badge}`, `**Type**: {work_item_type}`, `**Started**: {item_started_at ISO 8601}`, `**Completed**: {item_completed_at ISO 8601 or "—"}`, `**Total wall-clock**: {human-format duration}`, `**Generated**: {generated_at ISO 8601}`

2. **Retry hotspots**
   - `## Retry Hotspots`
   - If `hotspots` empty: `No retries — clean run.` (exact wording per AC6).
   - Else a bullet list, one per hotspot, formatted: `- **S{NN}** \`{display_label}\` × {retry_count} (final: {final_status})`.

3. **Step timeline**
   - `## Step Timeline`
   - A table with columns: `Step | Label | Attempts | Final Status | Duration`.
   - One row per `StepRow` in `step_number` order.

4. **Fix cycle details**
   - `## Fix Cycles`
   - If no fix cycles on the item: `No fix cycles executed.`.
   - Else a grouped list, one group per step that had fix cycles. For each:
     - `### S{NN} {display_label}`
     - For each `FixCycleEntry`:
       - `#### Cycle {cycle_number} ({trigger_type}) — {status}, {duration_secs}s`
       - If `fix_summary` present: `> {fix_summary}` (blockquote; render multi-bullet summaries as a multi-line blockquote).
       - Else: `> _no fix summary captured (pre-F-00056)_` (exact wording per AC5).
       - Links: `Trigger report: {trigger_report}` and `Fix report: {fix_report}` if the paths exist.

Footer (outside the 4 sections, at the very end):

```
---
_Generated by iw item-report on {generated_at}._
```

Purity: the renderer is a pure function of `ExecutionReportData`. No DB access, no I/O. This guarantees `--stdout` and disk output are byte-identical (Invariant 8).

### 3. File-path resolution helper

```python
def resolve_report_path(
    session: Session, project_id: str, work_item_id: str
) -> Path: ...
```

Rules (design Boundary Behavior row "Item archived to .tar.zst already"):

1. Look up the project's `repo_root` via `session.get(Project, project_id).repo_root` (mirror the pattern used by `archive_work_item` in `orch/archive/archiver.py:52-56`). Resolve paths absolutely against `repo_root`, not the CLI's current working directory. Raise `ExecutionReportResolutionError` if the project is not found.
2. If `<repo_root>/ai-dev/active/<id>/` exists, return `<active_dir>/<id>_execution_report.md`.
3. Else if `<repo_root>/ai-dev/archive/<id>/` exists, return `<archive_dir>/<id>_execution_report.md`.
4. Else raise `ExecutionReportResolutionError` with a clear message. Do not create directories speculatively; callers decide whether to create the parent dir.

The CLI catches this error and exits with code 2 (Boundary Behavior row "Project directory resolution fails").

### 4. Writer function

```python
def write_execution_report(
    session: Session, project_id: str, work_item_id: str
) -> Path: ...
```

Calls `assemble_execution_report` → `render_execution_report_markdown` → writes to `resolve_report_path`. Returns the path written. Raises `ExecutionReportResolutionError` on path resolution failure.

### 5. `iw item-report` CLI command

Add to `orch/cli/item_commands.py` (mirror the style of an existing command like `item_status`):

```
iw item-report <item_id> [--project <pid>] [--stdout]
```

- `<item_id>`: required positional, format `F-NNNNN` / `I-NNNNN` / `CR-NNNNN`.
- `--project <pid>`: optional; defaults to the current project as resolved by existing CLI utilities.
- `--stdout`: optional flag; when set, print the rendered markdown to stdout and do not write to disk.

Exit codes:

- `0` on success (wrote file or printed to stdout).
- `2` on path resolution failure (`ExecutionReportResolutionError`).
- `1` on DB lookup failure (item not found — distinguish clearly in the error message).

Register the command in `orch/cli/main.py` if the existing pattern requires explicit registration; otherwise leave it auto-discovered.

### 6. Daemon auto-trigger in `_complete_item()`

In `orch/daemon/batch_manager.py`, extend `_complete_item()` to call `write_execution_report(...)` synchronously before the archive step. Requirements:

- Call it AFTER the status flip is persisted and committed (so the flipped status is visible to the assembly query) and BEFORE the archive handler picks the item up (Invariant 10). Do not reuse the same transaction.
- If `write_execution_report` raises any exception, log a WARNING with `project_id`, `work_item_id`, and the exception message, but DO NOT fail the completion transition (the item remains in its just-flipped status). Auto-generation is best-effort; the CLI is the authoritative path.
- Use the project's standard logger, not `print()`.

### 7. Fix-cycle summary ingestion in `orch/daemon/fix_cycle.py`

When the fix agent reports completion, the daemon already parses a JSON result payload. Extend the parsing:

- Expect an optional key `fix_summary` in the agent's result JSON (per the updated fix prompt templates).
- If present and non-empty, store the value in `FixCycle.fix_summary`, truncated to the first 20000 characters as a safety cap (Boundary Behavior row "Fix agent emits a multi-paragraph summary"). Agent contract guidance is 2000 chars; the 20000-char cap only activates for misbehaving agents.
- If absent, malformed, or empty, write NULL (not empty string) — Boundary Behavior row "Fix agent result missing fix_summary key".
- Never raise on a missing or malformed `fix_summary`; the rest of the cycle completion must succeed.

Persist inside the existing transaction that marks the FixCycle status (do not add a new transaction).

### 8. Edit three fix prompt templates

For each of:

- `ai-dev/templates/CodeReview_FIX_Prompt_Template.md`
- `ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md`
- `ai-dev/templates/QualityValidation_FIX_Prompt_Template.md`

Add to each template (after the existing Result Contract section, before end-of-file):

- A new requirement line in the contract: the `fix_summary` field is mandatory in the result JSON.
- In the result-contract JSON block, add `"fix_summary": "- bullet 1\n- bullet 2\n- bullet 3"` as a key with a realistic example. Add a note immediately after the JSON: `fix_summary: 1-3 bullets describing what was changed and why. Written verbatim to FixCycle.fix_summary and surfaced in the execution report. Keep under 2000 characters total.`

Do not renumber or reorder other sections.

### 9. DO NOT touch frontend, API, or tests

Frontend templates, dashboard routes, and tests are owned by later steps. This prompt's scope is backend + CLI + daemon + template contracts only.

## Project Conventions

Read the project's `CLAUDE.md` and `orch/CLAUDE.md` for:

- SQLAlchemy 2.0 sync style; `Mapped[]` fields; `select(...)` queries
- `DaemonEvent.metadata` is `event_metadata` in Python
- Click 8 for CLI; `@click.command`, `@click.argument`, `@click.option`
- Logging via `logging.getLogger(__name__)`, not `print`
- No `datetime.utcnow()`; use `datetime.now(tz=UTC)`

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Before implementing each public function (`assemble_execution_report`, `render_execution_report_markdown`, CLI command, ingestion), write a failing unit test in the equivalent `tests/unit/test_*.py` files named in the design's File Manifest. Minimum one test per function covering the happy path; add boundary-case tests as you go.
2. **GREEN**: Implement the minimum needed to pass.
3. **REFACTOR**: Clean up while keeping tests green.

Tests in this step exist to validate your implementation. S09 will add additional coverage.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit`
2. `make test-integration`
3. `uv run ruff check orch/ tests/`
4. `uv run mypy orch/`

Report `tests_passed: true` only if all four commands exit with code 0.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00056",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/execution_report.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py",
    "orch/cli/item_commands.py",
    "orch/cli/main.py",
    "ai-dev/templates/CodeReview_FIX_Prompt_Template.md",
    "ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md",
    "ai-dev/templates/QualityValidation_FIX_Prompt_Template.md"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
