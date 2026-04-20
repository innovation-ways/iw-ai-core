# F-00056_S04_CodeReview_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- Design document (Scope items 2-6, AC1, AC3, AC4, AC5, Boundary Behavior rows touching backend paths, Invariants 5, 8, 10, 12)
- `ai-dev/active/F-00056/reports/F-00056_S03_Backend_report.md` -- S03 report
- All files listed in S03's `files_changed`:
  - `orch/daemon/execution_report.py`
  - `orch/daemon/batch_manager.py` (diff only the `_complete_item()` region)
  - `orch/daemon/fix_cycle.py` (diff the fix-summary ingestion region)
  - `orch/cli/item_commands.py` (the new `item-report` command)
  - `orch/cli/main.py` (if modified)
  - `ai-dev/templates/CodeReview_FIX_Prompt_Template.md`
  - `ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md`
  - `ai-dev/templates/QualityValidation_FIX_Prompt_Template.md`

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S04_CodeReview_report.md`

## Review Checklist

### 1. Architecture Compliance

- `execution_report.py` contains only assembly + rendering + path resolution + write. No dashboard imports, no click imports.
- `render_execution_report_markdown` is pure (no DB access, no file I/O, no logging).
- The markdown renderer and disk writer share a single rendering call (Invariant 8: stdout and disk byte-identical).
- Per-project scoping on every DB query (Invariant 12). `WorkflowStep` / `StepRun` are scoped directly via `project_id` + `work_item_id`. `FixCycle` has NO `project_id` column; it is scoped transitively via `FixCycle.step_id → WorkflowStep.id` — the assembly query MUST JOIN `workflow_steps` and filter on `workflow_steps.project_id` or the query leaks cross-project rows. Flag any FixCycle query lacking this JOIN as a CRITICAL finding.
- The daemon hook in `_complete_item()` runs AFTER the item status flip is committed and BEFORE the archive step begins (Invariant 10). Note: `_complete_item()` already calls `db.commit()` (line ~650) before emitting the `item_completed` event; place the report-generation call between the commit and the event emit so the assembly query sees the committed status.
- Ingestion in `fix_cycle.py` persists inside the existing cycle-completion transaction; no new transactions introduced.

### 2. Code Quality

- `ExecutionReportResolutionError` (or equivalent) is caught at the CLI boundary and at the daemon hook boundary; neither path raises to the operator in a confusing way.
- `gantt_class` assignment matches the design's rules exactly; no unlabeled magic strings.
- Hotspot detection (`max_run_number >= 2`) and sort order (desc retry, asc step_number) match AC6 exactly.
- `display_label` fallback is consistent everywhere it's computed (factor into a helper if duplicated).
- CLI exit codes match S03's spec (0, 1, 2) and are documented in the help text.
- Logger usage: `logging.getLogger(__name__)`, not `print`.
- No `datetime.utcnow()`; use `datetime.now(tz=UTC)`.

### 3. Project Conventions

- Read `orch/CLAUDE.md` for CLI command group organization.
- Click option/argument style matches sibling commands.
- Type hints are complete on public APIs.
- Dataclasses are `frozen=True` where S03 mandated.

### 4. Security

- Safety-cap truncation at 20000 chars for over-long `fix_summary` (Boundary: multi-paragraph; the 2000-char number is agent-facing guidance only, not a DB truncation). Verify the cap is 20000, not 2000.
- Markdown renderer does NOT escape the `fix_summary` content in a way that breaks legitimate markdown, but also does NOT allow injection that would break the enclosing document structure. Reasonable: store verbatim, render as a blockquote where downstream rendering handles escaping.
- No path-traversal vulnerability in `resolve_report_path`. The `<id>` is validated as `F-NNNNN` / `I-NNNNN` / `CR-NNNNN` format (either by the CLI upstream or inside the resolver). Verify.
- No shell injection in any subprocess call (there should be none — flag if introduced).

### 5. Testing

- S03 added minimal TDD tests. Verify each public function has at least one happy-path test.
- S09 will expand coverage; absence of exhaustive edge-case tests in S03 is expected — do NOT flag as HIGH.
- Tests use Click's `CliRunner` for CLI tests (no subprocess spawns).

### 6. Fix Prompt Template Changes

- All three templates carry the new `fix_summary` contract requirement.
- The example value in each template is realistic (1-3 bullets).
- The note explaining `fix_summary` appears immediately after the JSON block.
- Other sections of each template are unchanged in wording, order, or numbering.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `uv run ruff check orch/`
4. `uv run mypy orch/`

## Severity Levels

See template; use the standard 5-level scale.

## Review Result Contract

Standard JSON. `verdict=pass` only if zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE.
