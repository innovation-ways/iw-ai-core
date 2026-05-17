# CR-00061_S12_SelfAssess_prompt

**Work Item**: CR-00061 -- Flaky test quarantine workflow (P2-CR-C)
**Step**: S12
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

You ANALYZE; you do not apply migrations.

## Input Files

- `$IW_ITEM_ID` (canonical item ID).
- `.worktrees/CR-00061/ai-dev/logs/` — run logs, fix-cycle logs.
- `ai-dev/active/CR-00061/reports/` — S01–S11 step reports.
- `ai-dev/active/CR-00059/reports/`, `ai-dev/active/CR-00060/reports/` — Phase-2 predecessors for cumulative comparison.
- `ai-dev/work/TESTS_ENHANCEMENT.md` — confirm Phase-2 items all DONE after this CR's edits.
- `ai-dev/active/CR-00061/CR-00061_CR_Design.md`

## Output Files

- `ai-dev/active/CR-00061/reports/CR-00061_self_assess_report.md`
- `ai-dev/active/CR-00061/reports/CR-00061_self_assess_findings.json`

## Context

This is the **closing Phase-2 CR**. After CR-00059 + CR-00060 + CR-00061 land, every Phase-2 item is DONE. Findings shape Phase-3 sizing and the Phase-3 CR template.

**Use the `iw-item-analyze` skill** to perform the analysis.

## Soft-Step Semantics

Does not block merge. Produce a usable report even if analysis is partial.

## Additional Phase-2-closing findings to surface

Beyond the generic `iw-item-analyze` rubric:

1. **Marker deselection foolproofness.** Did S01's SMOKE TEST in deliverable 7 work first try, or was there friction (e.g. addopts parsing surprise; `--strict-markers` interaction; pytest version mismatch)? If friction, document the lesson — Phase 3 will add more markers (3.4 cross-project isolation may add a `tenant_a` / `tenant_b` marker; 3.5 security may add a `negative` marker), and the addopts-merge pattern needs to be muscle-memory by then.

2. **Aggregator robustness.** Did S03's independent run on the SKIPPED-row fabricated log surface any parsing surprise (e.g. the regex matched SKIPPED rows and reported them as flakes)? If yes, file a follow-up `P2-CR-C-followup-aggregator-skipped-row-handling`.

3. **The file-an-incident rule enforceability.** This is a prose rule — no automated check. Did reviewers in S02 and S03 actually verify the rule's text was verbatim across the three documentation surfaces? If they had trouble, that's the signal that a small automated check (an `iw` CLI command, or a `make` target, that grep'd for `@pytest.mark.quarantine(` and asserted each one's `reason` contains `I-NNNNN`) would be worth a follow-up CR.

4. **Cumulative Phase-2 cost.** Sum: CR-00059 (3600 s S01 spike + S12 etc.) + CR-00060 (3000 s S01 + S12 etc.) + CR-00061 (1800 s S01 + S12 etc.) = approximate. Compare to Phase 1 (5 CRs over 5 days). Recommend whether Phase 3 should be sequenced (one CR at a time) or batched (multiple in parallel via the batch executor) based on cumulative cost so far.

5. **Which of the 3 Phase-2 CRs delivered the highest perceived value.** Best read by stepping back: did mutation testing find a surviving mutant that informed a real test improvement? Did Hypothesis surface a real bug? Did the quarantine workflow's smoke test reveal anything about the addopts mechanics? Rank the 3 CRs and recommend whether to invest more in any one direction (e.g. expand mutation scope sooner than P2-CR-A-followup currently plans).

6. **Phase-3 sequencing recommendation.** Phase 3 has 6 items (3.1 E2E layer; 3.2 contract sweep + schemathesis; 3.3 iw CLI contract; 3.4 cross-project isolation matrix; 3.5 security module; 3.6 data-layer module — partly done). Based on:
   - Cost cap learned from Phase 2 (per-CR wall-clock).
   - Which Phase-2 patterns are most reusable for which Phase-3 item (e.g. mutation testing's scope-restriction pattern fits 3.6 data-layer; Hypothesis's profile-pattern fits 3.4 cross-project).
   - Which Phase-3 item closes the most-incident-prone category.

   Recommend the FIRST Phase-3 CR by name. State your reasoning in 3–5 sentences.

7. **Patterns to bake into the Phase-3 template.** Across CR-00045 (TDD RED-evidence), CR-00052 (audit-table-as-deliverable), CR-00059 (measurement-table-as-deliverable + spike-then-setup), CR-00060 (full-setup + cross-doc-square + marker auto-apply hook), CR-00061 (smoke-test-and-revert + fabricated-fixture verification), there's a growing set of recurring deliverable shapes. Recommend which of these belongs in the Phase-3 standard template (e.g. "every Phase-3 CR with a marker change must include a SMOKE TEST capture in S01's report").

## TDD RED Evidence

S01's report MUST contain `tdd_red_evidence` with a real test id from `tests/unit/test_quarantine_marker_setup.py` + a real failure line (any of the 5 tests). `"n/a"` = CRITICAL finding (CR-00045 contract violation).

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00061",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00061/reports/CR-00061_self_assess_report.md",
    "ai-dev/active/CR-00061/reports/CR-00061_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Phase-2 closing CR (3rd of 3). Analysis includes 7 Phase-2-closing findings + a Phase-3 sequencing recommendation. Cumulative Phase-2 cost: <h:mm:ss>. Recommended next Phase-3 CR: <name>."
}
```
