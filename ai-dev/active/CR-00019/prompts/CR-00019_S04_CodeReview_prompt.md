# CR-00019_S04_CodeReview_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step Being Reviewed**: S03 (backend-impl — skill contract)
**Review Step**: S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards as every other prompt in this CR. Read `docs/IW_AI_Core_Agent_Constraints.md` if unsure.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md`
- `ai-dev/work/CR-00019/reports/CR-00019_S03_Backend_report.md`
- All files listed in the S03 report's `files_changed`

## Output Files

- `ai-dev/work/CR-00019/reports/CR-00019_S04_CodeReview_report.md`

## Context

You are reviewing S03: the skill contract change (rationale + `--check` filter + dropping always-try fixes + mirror sync).

## Review Checklist

### 1. Skill correctness

- Does `run_make_oss` actually skip findings not in `check_ids` when the filter is provided?
- Is the always-try block (`OSS-ENV-03`, `OSS-ENV-04`, `OSS-SEC-04`, `PRE-COMMIT-CONFIG`) fully deleted — no leftover reference, no "legacy fallback" comment?
- Does argparse reject `--check` outside make_oss mode? Does it reject make_oss without `--check`?
- Does `Finding.to_dict()` include `rationale`?

### 2. Rationale content quality

Spot-check 5 random check modules. For each:
- Is the rationale a coherent 2–4 sentences? Not a restatement of the summary?
- Does it explain *why* the check exists, not *what* the check does?
- Is the tone calm and explanatory (not preachy, not salesy, not marketing-speak)?
- Is it free of placeholder text like "TODO" or "TBD"?

Reject the review if more than one module has placeholder rationales or rationales that just paraphrase the summary.

### 3. Coverage

- Does every `Finding(...)` constructor in `scripts/checks/*.py` carry `rationale=...`?
- Run a grep for `Finding\(` across `scripts/checks/*.py` and verify each call site has a rationale kwarg. List any that don't.

### 4. Persistence pass-through

- Does `orch/oss/persistence.py` pass the rationale into the `OssFinding` row?
- Does it tolerate a scanner that outputs older data without a rationale key (backward compatibility with pre-migration scans)?

### 5. Mirror sync

- `diff -rq skills/iw-oss-publish/ .claude/skills/iw-oss-publish/` — must be empty (modulo `__pycache__`).
- Flag as CRITICAL if the mirror is out of date.

### 6. Project conventions

Read `CLAUDE.md`. Check:
- Modern typing (no `Optional[X]`, use `X | None`).
- No `os.path` / `pathlib` mixed styles — match what the file already uses.
- Logging conventions (module-level `logger`).
- README is up to date with the dropped always-try list and `--check` usage.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — zero failures.
2. `make lint` — clean.
3. `uv run mypy orch/ dashboard/` — clean.
4. Re-run S03's unit tests — all pass.
5. Mirror diff empty.

## Severity Levels

Standard (see S02 for the table). A missing rationale on even one finding → HIGH. A mirror diff → CRITICAL. An orphaned always-try reference → HIGH.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00019",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
