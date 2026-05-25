# CR-00085_S13_SelfAssess_prompt

**Work Item**: CR-00085 -- DB-column documentation gate
**Step**: S13
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps`/`inspect`/`logs` permitted. You analyze; you do not modify.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This work item adds no migration. Reject any migration file appearing in any step report's `files_changed`.

## Input Files

- **Item ID** — `$IW_ITEM_ID` (canonical source).
- **Worktree logs** — `.worktrees/CR-00085/ai-dev/logs/`.
- **Item reports dir** — `ai-dev/work/CR-00085/reports/`.

## Output Files

- `ai-dev/work/CR-00085/reports/CR-00085_self_assess_report.md` — narrative.
- `ai-dev/work/CR-00085/reports/CR-00085_self_assess_findings.json` — structured findings.

## Context

Self-assessment of CR-00085 (DB-column documentation gate). Use the `iw-item-analyze` skill end-to-end — the skill is the source of truth for the output contract and procedure. Do not re-implement the analysis inline.

In Claude Code, invoke via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode the skill is auto-loaded.

## Item-specific things to look for

When the skill produces findings, pay particular attention to the following CR-00085-specific risks:

1. **Did S01 walk `Base.registry.mappers` correctly?** The most likely failure mode in this CR is a scanner that uses python `__dict__` reflection, trips over `Base.metadata`, and misses the `event_metadata` rename. Check whether S03/S04 caught it OR whether a QV gate (especially `unit-tests`) caught it via the regression test. If a fix cycle was burned diagnosing reserved-name handling, surface that as a finding (S01 prompt was explicit — was it heeded?).

2. **Did the baseline file end up sorted and stable?** A non-deterministic baseline (different sort order per run) produces noisy diffs and erodes trust in the gate. Look for any fix-cycle or report mentioning baseline-diff churn.

3. **Did S02 honour the warn-first `|| true` policy in both surfaces?** Look at whether S03 / S04 / a QV gate caught a missing `|| true` on either the Makefile `quality` chain or the GH workflow step. A blocking gate on either surface contradicts the CR's burn-in design and would be a CRITICAL self-assess finding even if it shipped.

4. **Did the baseline entry count appear consistently across all surfaces?** Cross-reference: S01's `tdd_red_evidence`, the tracker §11 changelog, the design's Notes section, the strategy doc §5 row. Drift among these means the wiring step was sloppy.

5. **Was scope discipline maintained?** Check `git diff main --name-only` against the design's Impacted Paths. The CR forbids any edit to `orch/db/models.py`, `docs/IW_AI_Core_Database_Schema.md`, or migration files. A diff outside the allow-list is a CRITICAL finding.

6. **Compare to CR-00046's pattern.** The two scanner kits are structurally identical; if this CR's S01 took materially longer (more retries, more fix-cycles) than CR-00046's analogous step, surface what changed. Was the design less precise? Was the agent confused by the SQLAlchemy reflection API? Were there prompt-template improvements that drifted away?

7. **TDD RED-evidence quality.** S01 is the only behaviour step. Verify `tdd_red_evidence` captured the pre-implementation `ModuleNotFoundError` / `ImportError`, not a post-hoc "n/a" or an `AssertionError` that would mean the scanner already existed when the test ran.

## Soft-Step Semantics

This step's failure does NOT block merge — produce the best report you can. If the analysis cannot complete, write a stub report explaining why and emit `findings: []`.

## TDD RED Evidence

S01 is a behaviour-implementing step (`backend-impl`). Verify the report's `tdd_red_evidence` field carries the pre-implementation failure line.

S02 is a wiring step. The `"n/a — Makefile/CI/docs/skill/tracker wiring only, no production logic"` form is acceptable.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "self-assess-impl",
  "work_item": "CR-00085",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00085/reports/CR-00085_self_assess_report.md",
    "ai-dev/work/CR-00085/reports/CR-00085_self_assess_findings.json"
  ],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
