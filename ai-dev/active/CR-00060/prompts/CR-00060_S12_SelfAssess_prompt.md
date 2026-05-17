# CR-00060_S12_SelfAssess_prompt

**Work Item**: CR-00060 -- Hypothesis property-based tests on the state machines (P2-CR-B)
**Step**: S12
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read-only introspection + testcontainer fixtures allowed.

## ⛔ Migrations: agents generate, daemon applies

You ANALYZE; you do not apply migrations.

## Input Files

- `$IW_ITEM_ID` (canonical item ID).
- `.worktrees/CR-00060/ai-dev/logs/` — run logs, fix-cycle logs.
- `ai-dev/active/CR-00060/reports/` — S01–S11 step reports.
- `ai-dev/active/CR-00060/evidences/pre/cr-00060-profile-wall-clock.txt`
- `ai-dev/active/CR-00059/reports/` — for cross-CR comparison (CR-00059 was the 1st Phase-2 CR).
- `ai-dev/active/CR-00060/CR-00060_CR_Design.md`

## Output Files

- `ai-dev/active/CR-00060/reports/CR-00060_self_assess_report.md`
- `ai-dev/active/CR-00060/reports/CR-00060_self_assess_findings.json`

## Context

You are running the self-assessment step for **CR-00060 — Hypothesis property-based tests (P2-CR-B)**, the **2nd Phase-2 CR**. Findings shape the structure and scope of P2-CR-C (item 2.3, flaky/quarantine workflow) and feed back into the Phase-2 CR template.

**Use the `iw-item-analyze` skill** to perform the analysis.

## Soft-Step Semantics

This step does not block merge. Produce a usable report even if analysis is partial.

## Additional Phase-2-specific findings to surface

Beyond the generic `iw-item-analyze` rubric:

1. **Full-setup vs spike-then-setup.** CR-00059 used spike-then-setup; CR-00060 used full-setup with 5 modules in one CR. Compare:
   - S01 wall-clock + iteration count: which shape converged faster?
   - Number of S02/S03 findings: which shape produced cleaner output?
   - Number of fix cycles: which shape had less rework?
   - Recommend a default shape for the next Phase-2 CR (P2-CR-C).

2. **Real bugs found.** Did any property test surface a real production bug? Two places to check:
   - During S01's GREEN-running iteration: did Hypothesis shrink a failure that turned out to be a real bug (vs an incorrect invariant statement)?
   - During S03's deep-profile sweep: same question at higher coverage.
   - Each real bug found = headline value-add for the CR. Note them by name + the shrunk counterexample.

3. **`ci` profile budget calibration.** Was the 30s budget the right call?
   - Actual `ci` wall-clock from `cr-00060-profile-wall-clock.txt` ÷ 30s = utilisation %.
   - If <50% utilised, recommend raising `max_examples` (more coverage at no real cost).
   - If close to 30s, recommend either keeping or tightening — Phase-3 CRs will add more tests to `make test-unit`.

4. **The marker auto-apply hook pattern.** Was it clean to add? Did reviewers struggle to verify it?
   - If clean, recommend reusing it for the `quarantine` marker in P2-CR-C.
   - If problematic (e.g. ordering issues with other conftest hooks), document the friction.

5. **DB-backed property test placement.** `test_iw_next_id_atomicity_properties.py` lives in `tests/unit/properties/` despite needing a testcontainer (via `pytest_plugins`). Did that placement create friction in `make test-unit` runs? (E.g. testcontainer startup cost newly visible in unit-test wall-clock.) Inform whether future DB-backed properties should go in a separate `tests/integration/properties/` dir.

6. **`compute_batch_status` extraction (if it happened).** Was the extraction surgical? Did existing batch tests pass identically? If the extraction was rejected (S01 raised the blocker and filed `P2-CR-B-followup-batch-helper-extraction`), note how that decision was reached and whether earlier recon would have caught the entanglement.

7. **Cumulative Phase-2 cost.** Sum: CR-00059 total wall-clock (S01–S12) + CR-00060 total wall-clock + S03's deep-profile run. Compare to the budget: was Phase 2's per-CR cost comparable to Phase 1's, or higher? Inform whether P2-CR-C should be smaller-scoped.

8. **Phase-3 forward-look.** Phase 3 starts after item 2.3 lands. Phase-3 items (E2E layer, contract-sweep, CLI-contract layer, cross-project isolation, security module, data-layer module) are bigger and more cross-cutting. Surface any Phase-2 lessons that should bake into the Phase-3 template:
   - audit-table-as-deliverable (CR-00052) — useful for Phase-3 enumeration steps?
   - measurement-table-as-deliverable (CR-00059) — useful for Phase-3 performance-budget steps?
   - the cross-doc-square check (this CR's S03) — useful for any Phase-3 multi-doc CR?

## TDD RED Evidence

S01's report MUST contain `tdd_red_evidence` with a real test id from `tests/unit/test_hypothesis_setup.py` + a real failure line (ImportError/ModuleNotFoundError/AssertionError/KeyError — all acceptable for this CR's RED, since hypothesis is genuinely absent pre-patch). `"n/a"` = CRITICAL finding (CR-00045 contract violation — this is a behavioural step).

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00060",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00060/reports/CR-00060_self_assess_report.md",
    "ai-dev/active/CR-00060/reports/CR-00060_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Phase-2 2nd CR. Analysis includes 8 Phase-2-specific findings. Recommendations for P2-CR-C structure and Phase-3 template."
}
```
