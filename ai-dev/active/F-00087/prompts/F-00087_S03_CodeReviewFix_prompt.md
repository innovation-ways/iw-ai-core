# F-00087_S03_CodeReviewFix_prompt

**Work Item**: F-00087 -- Pi runtime + per-tab runtime selection in AI Assistant chat
**Fix Cycle**: 1 of 5 (subsequent cycles auto-renumber)
**Original Step**: S01 (backend-impl)
**Review That Triggered Fix**: S02

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migration in this Feature.)

## Input Files

- `ai-dev/active/F-00087/F-00087_Feature_Design.md` — design document (authoritative spec)
- `ai-dev/active/F-00087/reports/F-00087_S02_CodeReview_report.md` — review report with findings
- All files referenced in the findings

## Output Files

- `ai-dev/active/F-00087/reports/F-00087_S03_CodeReview_FIX_report.md`

## Context

The S02 code review for S01 flagged CRITICAL / HIGH / MEDIUM(fixable) findings on the Pi backend layer. Apply **only** those findings; no unrelated refactors.

## Design Doc — Source of Truth (READ FIRST)

`ai-dev/active/F-00087/F-00087_Feature_Design.md` is authoritative. Read §Scope, §Invariants, §Boundary Behavior before applying any fix.

**The design doc wins when findings disagree.** R-00072 §2's "LF-only JSONL framing" is a hard requirement — if a finding suggests "use readline() because it's simpler", refuse, document in `findings_skipped`, and keep the byte-level reader.

## Diagnostic Hypothesis — Findings to Address

Read each finding from `F-00087_S02_CodeReview_report.md`. Each is one hypothesis from the reviewer — verify against the spec before applying.

## Pre-fix Procedure

1. Read the design doc end-to-end (Scope, Invariants, Boundary Behavior, TDD Approach).
2. For each finding: diff the target file against the spec; list deviations before editing.
3. Apply the minimum patch. Findings should resolve as a side effect of aligning with the spec.
4. Special care for `pi_jsonl_reader.py` — any "simplification" that introduces a Python built-in line iterator is a regression; if a reviewer flags the code as "complex", document the constraint and keep the byte-level reader.

## Constraints

1. **Only fix flagged issues.** No unrelated refactors.
2. **Preserve subprocess lifecycle semantics** — lazy spawn, LRU eviction, idle reaper. Don't accidentally eager-spawn at create_session time.
3. Follow project conventions in `CLAUDE.md`, `orch/CLAUDE.md`, `tests/CLAUDE.md`.
4. **Run targeted tests after every fix.**

## Escalation

Fix cycle 1 of 5. Prefer honest escalation. On cycle 5, populate `findings_skipped` with clear explanation.

## Test Verification (NON-NEGOTIABLE)

After applying fixes, run targeted tests on the F-00087 surface (S11/S12 own full-suite execution):

```bash
uv run pytest tests/unit/chat/test_pi_jsonl_reader.py -v
uv run pytest tests/unit/chat/test_pi_runtime_lru_eviction.py -v
make lint
make typecheck
```

Do NOT report `tests_passed: true` unless every targeted test passes with zero failures.

## Fix Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-fix-impl",
  "work_item": "F-00087",
  "fix_cycle": 1,
  "review_step": "S02",
  "findings_addressed": [
    {
      "finding_number": 1,
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE",
      "status": "fixed|partially_fixed",
      "files_changed": ["path/to/file.py"],
      "description": ""
    }
  ],
  "findings_skipped": [],
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
