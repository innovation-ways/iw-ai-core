# F-00087_S07_CodeReviewFix_Final_prompt

**Work Item**: F-00087 -- Pi runtime + per-tab runtime selection in AI Assistant chat
**Fix Cycle**: 1 of 5 (subsequent cycles auto-renumber)
**Original Steps**: S01..S05
**Review That Triggered Fix**: S06 (Final Review)

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migration in this Feature.)

## Input Files

- `ai-dev/active/F-00087/F-00087_Feature_Design.md` — design document (authoritative spec)
- `ai-dev/active/F-00087/reports/F-00087_S06_CodeReview_Final_report.md` — final review report with findings
- All files referenced in the findings

## Output Files

- `ai-dev/active/F-00087/reports/F-00087_S07_CodeReview_FIX_Final_report.md`

## Context

The S06 final cross-agent review flagged CRITICAL / HIGH / MEDIUM(fixable) findings and possibly missing requirements. Cross-cutting fixes (Python ↔ TypeScript ↔ frontend ↔ tests) may require coordinated changes across multiple modules — that is expected. Apply only those findings.

## Design Doc — Source of Truth (READ FIRST)

Read `ai-dev/active/F-00087/F-00087_Feature_Design.md` end-to-end. The Pi backend ↔ TypeScript extension ↔ frontend contract is tight; final-review fixes often span three layers at once.

**The design doc wins when findings disagree.** R-00072 §2 (LF-only JSONL framing) is a hard requirement — never replace with `readline()` for "simplicity".

## Diagnostic Hypothesis — Findings to Address

Read each finding in `F-00087_S06_CodeReview_Final_report.md`. Each is one hypothesis; verify against the spec before applying.

## Missing Requirements

If the final review identified missing requirements, implement them following the design spec, TDD-first (write a failing test, then minimal implementation).

## Pre-fix Procedure

1. Read the design doc end-to-end.
2. For each finding (and missing requirement): diff the affected module(s) against the spec; list deviations.
3. Apply the minimum patch that aligns code with the spec across all affected layers.
4. Cross-cutting fixes: ensure consistency between Python normalizer, TypeScript extension, and frontend dropdown contracts.
5. If a finding disagrees with the spec, document in `findings_skipped` and follow the spec.

## Constraints

1. **Only fix flagged issues and implement missing requirements.** No unrelated refactors.
2. **Preserve subprocess lifecycle semantics** — lazy spawn, LRU eviction, idle reaper.
3. **Preserve LF-only JSONL framing** — never replace the byte-level reader with a built-in line iterator.
4. **Cross-cutting consistency** — when fixing one layer, propagate to dependent layers in the same fix cycle.
5. Follow project conventions in `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `tests/CLAUDE.md`.

## Escalation

Fix cycle 1 of 5. Prefer honest escalation. On cycle 5, populate `findings_skipped` with clear explanation.

## Test Verification (NON-NEGOTIABLE)

After applying fixes, run targeted tests on the F-00087 surface (S11/S12 own full-suite execution):

```bash
uv run pytest tests/unit/chat/test_pi_*.py tests/unit/chat/test_sync_agents_extensions.py tests/unit/chat/test_tab_service_allowlist.py -v
uv run pytest tests/integration/test_chat_pi_*.py -v
make lint
make typecheck
```

Do NOT report `tests_passed: true` unless every targeted test passes with zero failures.

## Fix Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-fix-final-impl",
  "work_item": "F-00087",
  "fix_cycle": 1,
  "review_step": "S06",
  "findings_addressed": [
    {
      "finding_number": 1,
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE",
      "status": "fixed|partially_fixed",
      "files_changed": [],
      "description": ""
    }
  ],
  "missing_requirements_implemented": [],
  "findings_skipped": [],
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
