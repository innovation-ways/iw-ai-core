# I-00102_S06_CodeReviewFinal_prompt

**Work Item**: I-00102 — iw register silently ignores design-package drift; approve must auto-refresh workflow_steps
**Scope**: Cross-agent final review across S01..S05
**Step**: S06
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## Input Files

- **Runtime step state** — `uv run iw item-status I-00102 --json`.
- `ai-dev/active/I-00102/I-00102_Issue_Design.md` — acceptance contract.
- `ai-dev/active/I-00102/I-00102_Functional.md` — functional summary.
- All reports under `ai-dev/active/I-00102/reports/` and `ai-dev/work/I-00102/reports/`.
- Every file in the union of all `files_changed` lists across S01–S05.

## Output Files

- `ai-dev/active/I-00102/reports/I-00102_S06_CodeReviewFinal_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
make typecheck
```

Any new violation in a changed file = **CRITICAL** finding.

## Review Focus — what S04 cannot see

S04 reviewed each agent's deliverables in isolation. Your job is the cross-cutting view:

### 1. Acceptance criteria coverage

For each AC in the design (AC1 auto-refresh on drift, AC2 reproduction test, AC3 refusal-on-non-draft, AC4 digest determinism, AC5 backfill-safe migration): name the specific code path + the specific test that pins it. If an AC has no test, that is a **CRITICAL** finding.

### 2. Functional contract honesty

The functional doc tells operators "When you edit a work item's design after first registering it, the approve action now notices the change automatically and updates the recorded steps to match what is on disk." Verify the implementation actually delivers that — re-read the approve path end-to-end. If the functional doc claims behaviour the code doesn't implement, flag as **HIGH**.

### 3. Daemon interaction

The companion fix on `fix/daemon-prompt-file-missing-fail-fast` raises `PromptFileMissingError` when `step.prompt_file` is set but missing. After I-00102 lands, that path SHOULD become unreachable for `draft → approved` items (auto-refresh would have rebuilt the rows correctly). Verify the integration test suite covers the no-drift-after-approve invariant — i.e. an item that approves cleanly never has a drifted `prompt_file`. If the test surface leaves this gap, flag as **HIGH** (with a recommended additional test in S07's scope).

### 4. Single source of truth for step insertion

Both `register` and the new approve-time refresh insert `workflow_steps`. Verify they share the same helper function (no copy-paste). If they diverge, future register-side changes can re-introduce drift between the two code paths — flag as **HIGH**.

### 5. Transaction atomicity

The drift-rebuild + status flip + daemon-event insert all happen under one transaction. Verify this is true (single `with get_session():` block) and that any exception during rebuild rolls back ALL of them. The S03 test `test_approve_drift_rebuild_is_atomic_on_failure` should prove this — verify it asserts the right invariants (counts unchanged, digest unchanged, status unchanged, no event recorded).

### 6. Phantom-skip ordering

`auto_skip_phantom_qv_gates` runs after the rebuild. Verify the ordering is correct (rebuild → phantom-skip → status flip) and that phantom-skipping operates on the freshly-rebuilt rows, not the deleted ones. A regression that flips the order would leave skipped rows belonging to a different layout.

### 7. Backfill-safe migration check

The S01 migration is nullable, no default. The S02 approve path treats NULL as drift and refreshes on first hit. Verify both halves together produce safe backfill: no in-flight item gets its rows rebuilt unintentionally (only `draft` items are eligible, and approve is the only entry to the refresh path).

### 8. Lint / format / mypy hygiene

Re-run the gates against the union of changed files. Any new violation is **CRITICAL**.

### 9. Test mutation check

Pick three production lines from the diff (one in each of: digest helper, approve rebuild, daemon-event insert). Mentally delete each; confirm at least one assertion in S03's test suite would fail. If a line has no test coverage, flag as **HIGH** with a recommended test name.

### 10. Scope discipline

Verify the diff stays within `scope.allowed_paths` from the workflow manifest. Any out-of-scope edit is **CRITICAL**.

## Output Report Shape

`Findings` section grouped by severity (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_INFO / LOW). Each finding: `file:line`, description, rationale, recommended fix. Top of report has the per-AC traceability table (AC → code-path → test).

## Subagent Result Contract

```bash
mkdir -p ai-dev/active/I-00102/reports
uv run iw step-done I-00102 --step S06 \
  --report ai-dev/active/I-00102/reports/I-00102_S06_CodeReviewFinal_report.md
```

```json
{
  "step": "S06",
  "agent": "code-review-final-impl",
  "work_item": "I-00102",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/I-00102/reports/I-00102_S06_CodeReviewFinal_report.md"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "review only — no tests run",
  "tdd_red_evidence": "n/a — review step",
  "verdict": "pass|pass_with_fixes|fail",
  "ac_coverage": {
    "AC1": "<code_path> + <test_name>",
    "AC2": "<test_name>",
    "AC3": "<code_path> + <test_name>",
    "AC4": "<test_name>",
    "AC5": "<code_path> + <test_name>"
  },
  "findings_count": {
    "critical": 0,
    "high": 0,
    "medium_fixable": 0,
    "medium_info": 0,
    "low": 0
  },
  "blockers": [],
  "notes": ""
}
```
