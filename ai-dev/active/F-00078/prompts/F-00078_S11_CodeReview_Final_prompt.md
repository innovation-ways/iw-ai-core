# F-00078_S11_CodeReview_Final_prompt

**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Review Step**: S11 (Final Review)
**Implementation Steps Reviewed**: S01..S09

---

## ⛔ Docker is off-limits

See S01 prompt for full text. Same rules apply.

## ⛔ Migrations: agents generate, daemon applies

See S01 prompt. Same rules apply.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00078 --json`.
- `ai-dev/active/F-00078/F-00078_Feature_Design.md` -- Design document
- All implementation step reports: `ai-dev/work/F-00078/reports/F-00078_S{01,03,05,07,09}_*_report.md`
- All per-agent code review reports: `ai-dev/work/F-00078/reports/F-00078_S{02,04,06,08,10}_CodeReview_report.md`
- All files listed in all implementation reports' `files_changed`

## Output Files

- `ai-dev/work/F-00078/reports/F-00078_S11_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for **F-00078: Per-project self-assessment step with copy-paste fix prompts**.

This review looks at the complete picture — not individual steps in isolation, but how everything fits together. Per-agent reviews have already been done; your job is to catch cross-cutting issues they could not.

The feature spans five layers:
- **DB**: new enum value (S01)
- **Backend**: project flag, helpers, soft-step semantics, CLI flag (S03)
- **Frontend**: report assembler + Jinja2 fragment (S05)
- **Skills/Templates**: skill migration + design-skill injection (S07)
- **Tests**: comprehensive coverage (S09)

The cross-cutting risks:
- **Schema drift between layers**: the findings JSON shape produced by the migrated skill (S07) MUST be parseable by `orch/self_assess.py` (S03) AND renderable by the dashboard fragment (S05). All three reference the same shape — verify they're consistent.
- **Step-injection consistency**: the design skills (S07) document a step format; the daemon's batch_manager (S03) handles soft-step semantics; the dashboard (S05) renders the report. If the design skills inject a step with `agent: "self-assess"` but S03's `is_self_assess_step()` checks `step_type == StepType.self_assess`, those don't match unless the step's `step_type` is explicitly set in the manifest. Verify the manifest schema is internally consistent.
- **`IW_ITEM_ID` env var**: claimed by S03 (export from executor) and consumed by S07 (skill body). If S03 didn't actually add the export and the skill body relies on it, the step will fail at runtime — verify by reading the executor scripts and the skill body together.

Read the design document to understand the full intended scope. Read all implementation and review reports to understand what was built. Then review all changed files holistically.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on ALL changed files:

```bash
make lint
make format-check
```

NEW violations → CRITICAL `category: conventions`.

## Review Checklist

### 1. Completeness vs Design Document

- Are ALL "In Scope" items implemented?
- Are ALL Acceptance Criteria covered by code AND tests?
- Are ALL Boundary Behavior rows handled (each becomes a test case)?
- Are ALL Invariants enforced or asserted?
- Any TODO comments or placeholder implementations?

Cross-reference S09's coverage matrix with the design doc; flag any AC/Boundary/Invariant with no implementation OR no test as MISSING_REQUIREMENT (CRITICAL).

### 2. Cross-Layer Consistency (the big one)

- **Findings JSON schema**: open `skills/iw-item-analyze/SKILL.md` and `orch/self_assess.py`. The fields documented in the skill's JSON example MUST match the parser's required fields. Mismatch → CRITICAL.
- **Step type identification**: open `orch/self_assess.py:is_self_assess_step` and the design skills' injected step JSON. The skill emits `"step_type": "self_assess"` (or equivalent) — does the daemon's manifest loader populate `WorkflowStep.step_type` from this field? Read `orch/cli/project_commands.py` (the `iw register` flow) to confirm. If the manifest field name doesn't match what `iw register` reads, the step will land with `step_type=implementation` and the soft-step semantics will not fire. CRITICAL if mismatched.
- **Sidecar path convention**: `findings_path_for` in `orch/self_assess.py` derives the JSON path from the report path. The skill writes to `<reports_dir>/<ID>_self_assess_findings.json`. The dashboard reads via `findings_path_for(step_run.report_file)`. All three must agree on the naming. Trace through with a concrete example (e.g., `ai-dev/work/F-00078/reports/F-00078_S<NN>_self_assess_report.md`) and verify the derived JSON path matches what the skill writes. Mismatch → HIGH.
- **`IW_ITEM_ID` env var**: grep for `IW_ITEM_ID` in `executor/`, `orch/daemon/`, and `skills/iw-item-analyze/SKILL.md`. The executor must export it; the skill must reference it. Either side missing → CRITICAL.

### 3. Integration Points

- Does the soft-step branching in `batch_manager.py` actually fire? Trace from `BatchItemStatus.executing` → `mark_item_completed` → `process_merge_queue`. If self_assess failure short-circuits at the wrong place, the batch_item could get stuck. HIGH.
- Does `assemble_execution_report` correctly handle the case where the self_assess step ran but `report_file` is None? (StepRun.report_file might be None if step-done was called without --report.) HIGH if it crashes.
- Does the `iw register` flow correctly accept and persist a manifest containing a `self_assess` step? Run a smoke check: `iw register F-00078 ... --steps-from <manifest>` should succeed against a manifest with the new step type.

### 4. Test Coverage (Holistic)

- Is there an end-to-end integration test that:
  1. Seeds a Project with `self_assess_enabled=True`
  2. Creates a WorkItem + workflow steps including a self_assess step
  3. Simulates the self_assess step running and writing both files
  4. Asserts the dashboard render includes the section AND the batch_item proceeds to merging

  This is the "all five layers wired correctly" smoke test. If missing, MEDIUM_FIXABLE (S09 may have decided this was out of scope, but it's worth flagging).

### 5. Architecture Compliance

- Read `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `tests/CLAUDE.md` for hard rules.
- Critical rules to verify:
  - No `docker compose up` or similar in any new code.
  - No `alembic upgrade` in any new code (S01's migration is the file only).
  - No live-DB connections in tests.
  - No `importlib.reload(orch.config)` in tests.
  - `dashboard/static/styles.css` regenerated if new Tailwind classes were added.

### 6. Security (Cross-Cutting)

- The `paste_prompt` strings flow from agent-generated content → JSON file → parser → dashboard template. Verify there's no path where they're rendered un-escaped (i.e., no `| safe` filter in the template, no `dangerouslySetInnerHTML` equivalent).
- The Jinja2 autoescape default applies to `paste_prompt`, `title`, `recommendation`, `bottom_line`, `coverage_notes`, `evidence` items. Confirm none use `| safe`.
- The findings JSON file is written by an agent inside a worktree — it's effectively trusted input but should still be parsed defensively. The parser should reject paths or schemes it doesn't understand.

### 7. Convention Drift

- New code follows the project's snake_case / Mapped[] / dataclass conventions.
- Imports organized correctly (stdlib → third-party → first-party).
- Logger names use `__name__`.
- No new top-level mutable state.

## Test Verification (NON-NEGOTIABLE)

Before submitting:

1. Run `make test-unit` — must pass.
2. Run `make test-integration` — must pass.
3. Run `make lint`, `make format-check`, `make type-check` — all must pass.
4. If any test is failing, this is a CRITICAL finding (broken merge readiness).

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Cross-layer schema mismatch; missing step_type in manifest plumbing; XSS via \|safe; missing IW_ITEM_ID; missing requirement; failing test | Must fix before merge |
| **HIGH** | Sidecar path mismatch; soft-step branching wrong; integration gap; out-of-scope changes | Must fix before merge |
| **MEDIUM (fixable)** | Missing e2e smoke test; convention drift; coverage gap | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Refactor opportunity; cleaner abstraction | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S11",
  "agent": "code-review-final-impl",
  "work_item": "F-00078",
  "steps_reviewed": ["S01", "S03", "S05", "S07", "S09"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "...",
      "suggestion": "...",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": "Document the cross-layer schema cross-check explicitly: skill JSON example fields ↔ parser required fields ↔ template rendered fields."
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
- `missing_requirements`: any AC/Invariant with no implementation. Each is automatically CRITICAL.
- `cross_cutting`: true on findings spanning multiple agents' work.
