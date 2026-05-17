# CR-00055_S12_SelfAssess_prompt

**Work Item**: CR-00055 -- Re-enable pytest-randomly by default — per-test PostgreSQL template-clone (P1-CR-C-followup-randomly-v2)
**Step**: S12
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps` / `docker inspect` / `docker logs` are allowed for diagnostic purposes; no state-changing operations.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. Your job is to ANALYZE the item's execution, not to modify the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source — expected `CR-00055`).
- **Worktree logs** — `.worktrees/CR-00055/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/CR-00055/reports/` — existing step reports (secondary evidence only).
- **Predecessor work-item context** (READ for cross-reference patterns):
  - CR-00048 (P1-CR-C — shipped 2026-05-13 with `-p no:randomly` fallback).
  - CR-00049 (P1-CR-C-followup-randomly — cancelled 2026-05-16 after the per-test TRUNCATE-CASCADE design caused a 3× perf regression and the per-module TRUNCATE fallback left ~230 within-module failures).
  - R-00077 (the research that produced this CR's strategy).

## Output Files

- `ai-dev/active/CR-00055/reports/CR-00055_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/CR-00055/reports/CR-00055_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00055**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## CR-00055-specific cross-references

When writing the narrative report, in addition to the standard `iw-item-analyze` checklist, address these specific questions arising from this CR's lineage (CR-00048 fallback + CR-00049 cancellation + R-00077 research + the 2026-05-16 spike validation):

1. **Did the spike-reference + R-00077 outline keep S01 inside its budget?** The 4 800 s S01 timeout was set on the assumption that the agent would crib the spike's working code rather than re-derive it. If S01's wall-clock was close to 4 800 s, the prompt strategy may not have given enough specificity — recommend tightening the prompt's "deliverable 1 — crib from the spike" section in any future similar item.
2. **Did the implementing agent remember the WAL_LOG override?** This is the perf-cliff hinge (~10× difference). If the S01 report shows S09 (`make test-integration`) close to the 1 200 s budget, the override may have been forgotten or partially applied. Recommend adding a CRITICAL grep-based check in S02's prompt.
3. **Did the implementing agent remember the `_pgtestdb_setup` re-export in `tests/dashboard/conftest.py`?** Without it, S09 hits hundreds of fixture-not-found errors. If S01 needed a fix cycle for this, recommend hardening the S01 prompt's "deliverable 4" section.
4. **Did any seed surface a new offender beyond the 3 known quarantines?** The spike on 2026-05-16 was definitive that 3 quarantines is enough across all 4 reference seeds. If S01 or S09 added a 4th quarantine, note it — the test suite has likely drifted since 2026-05-16 and a follow-up research update on R-00077 is warranted.
5. **Was the S09 wall-clock close to the 1 200 s budget?** If so, recommend bumping the budget for future randomisation work. The spike measured 10m54s on seed 12345 (single-process); under the QV pipeline with other load, the gate might be tighter.
6. **Did the implementing agent or any reviewer touch production code?** This CR's scope is tests + configs + docs only. Any production-code edit is scope creep and worth flagging.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence

The CR uses **the RED reproduction itself** as `tdd_red_evidence` — S01's deliverable 0 is the unfixed-state 4-seed sweep showing 271+ failures. No new behavioural tests are added; the existing 2 500+ tests passing under randomisation is the proof. When auditing the S01 report, expect `tdd_red_evidence` to reference the sweep counts, not a unit-test failure trace.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00055",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00055/reports/CR-00055_self_assess_report.md",
    "ai-dev/active/CR-00055/reports/CR-00055_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files. Cross-referenced CR-00048 + cancelled CR-00049 + R-00077 + the 2026-05-16 spike validation."
}
```

## Lifecycle Commands

```bash
uv run iw step-start CR-00055 --step S12
# ... run iw-item-analyze ...
uv run iw step-done CR-00055 --step S12 --report ai-dev/active/CR-00055/reports/CR-00055_self_assess_report.md
```
