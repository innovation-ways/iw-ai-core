# F-00078_S04_CodeReview_Backend_prompt

**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

See S01 prompt for full text. Same rules apply.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00078 --json`.
- `ai-dev/active/F-00078/F-00078_Feature_Design.md` -- Design document
- `ai-dev/work/F-00078/reports/F-00078_S03_Backend_report.md` -- S03 report
- All files listed in S03's `files_changed`

## Output Files

- `ai-dev/work/F-00078/reports/F-00078_S04_CodeReview_report.md` -- Review report

## Context

Review the backend implementation for F-00078. The S03 step:
1. Added `ProjectConfig.self_assess_enabled` and the projects.toml read path.
2. Created `orch/self_assess.py` with dataclasses, parser, and helpers.
3. Wired soft-step semantics into batch_manager / fix_cycle so self_assess failures don't block merge.
4. Added `--analysis-json` flag to `iw step-done`.
5. Registered the new `self-assess-impl` agent slug in `executor/step_executor_lib.sh` (`get_step_type` → `implementation`; `get_agent_label` → `SelfAssess`).
6. Possibly added `IW_ITEM_ID` env var injection in `executor/step_executor.sh`.

This is the largest step in the feature. Critical to catch:
- Soft-step semantics that accidentally suppress legitimate failures of OTHER step types.
- Parser laxity that accepts unsafe `target` values.
- Truthy-string bug on the `self_assess` projects.toml field.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violation in the changed files → CRITICAL finding (`category: conventions`).

## Review Checklist

### 1. Architecture compliance

- Does `orch/self_assess.py` live at the package root (not under `orch/daemon/` or `orch/cli/`)? It is consumed by both daemon and dashboard, so the package root is correct. Flag if it landed in the wrong subpackage.
- Does the soft-step branching live in the right place? The design doc explicitly calls for option (b): handle at batch_item progression, NOT at step-done time. If the agent moved it to `step_commands.py` and force-completed the StepRun, that's a HIGH finding (loses ground truth).
- Is `is_self_assess_step` in `orch/self_assess.py` (not duplicated in `browser_env.py`-style)?

### 2. Project flag handling

- Does the bool coercion guard against truthy strings? The design's Boundary Behavior row says non-bool values must default to `False` with a warning. If the agent used plain `bool(entry.get("self_assess", False))`, that's a HIGH finding because `bool("false") == True`.
- Is the warning logged at WARNING level (not DEBUG/INFO)?

### 3. Findings JSON parser

- Is `target` strictly validated against `{"iw-ai-core", "project"}`? Anything else must raise.
- Are unknown fields silently ignored (forward-compatible) rather than rejected?
- Are required fields enumerated in code (not just in a comment)? Missing `severity`, `target`, `recommendation`, or `paste_prompt` should raise.
- Is the parser tolerant of malformed JSON (raises a single domain exception, not a bare `JSONDecodeError`)?

### 4. Soft-step semantics

- Confirm: a `self_assess` step with `RunStatus.failed` does NOT trigger a `FixCycle` row.
- Confirm: a `self_assess` step with `RunStatus.failed` does NOT block transition from `executing` → `completed` → `merging` on the batch_item.
- Confirm: the `WorkflowStep.status` and `StepRun.status` values are NOT mutated to mask the failure — the dashboard must be able to show "self_assess failed" if it did.
- Confirm: NON-self_assess steps are unaffected — if the agent's branch is too broad (e.g., short-circuits `failed` for any "soft" step type they invented), that's a CRITICAL finding.

### 5. CLI flag

- Does `--analysis-json` raise `click.UsageError` if used on a non-self_assess step?
- Does it validate the path lives in the same parent dir as `--report` (defensive)? If it accepts arbitrary paths, that's a MEDIUM finding.
- Is the flag also added to `step-fail` per the design doc's "agent might fail with partial findings" note?

### 6. Executor env var

- Does the executor export `IW_ITEM_ID`? Verify by reading the executor scripts or the env-injection helper. If the agent claims they verified it but you can't find the export, ask them in your review (raise as a HIGH blocker rather than passing the review).

### 6b. Executor agent-slug registration

- Does `executor/step_executor_lib.sh::get_step_type()` have a case for `self-assess-impl` returning `"implementation"`? Without it, the executor will still default to `"implementation"` (so launches will work) but the case must be explicit so future grep / refactor finds it. Missing explicit case → MEDIUM_FIXABLE.
- Does `executor/step_executor_lib.sh::get_agent_label()` map `self-assess-impl` to `SelfAssess`? Missing → HIGH (report filenames will use the raw slug `self-assess-impl` and break the `_<Label>_report.md` naming convention used by S07's prompt template).
- Confirm the slug was NOT routed through the `browser` step type (that has custom env_up/env_down hooks that don't apply here). Wrong routing → CRITICAL.
- Confirm `get_fix_agent_for_review()` was NOT modified — `self-assess-impl` has no fix agent (soft-step; failures don't trigger fix cycles).

### 7. Test coverage (minimum bar — S09 will fill the rest)

- At minimum: parser unit tests for happy path + bad target + bad JSON; one integration test asserting self_assess failure doesn't block merge.
- If those are missing, MEDIUM_FIXABLE.

### 8. Out-of-scope

- Any change to `dashboard/`, `skills/`, `templates/design/` is out of scope for S03 → flag as HIGH so it gets redone in the right step.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

Both must pass. Specifically verify the new self_assess tests run.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Soft-step branching too broad (suppresses non-self_assess failures); R1/R2 violation | Must fix |
| **HIGH** | Bool-coercion bug; soft-step in wrong place; out-of-scope changes; missing IW_ITEM_ID | Must fix |
| **MEDIUM (fixable)** | Loose parser, missing CLI validation, weak test coverage | Should fix |
| **MEDIUM (suggestion)** | Refactor opportunity | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00078",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "...",
  "notes": ""
}
```
