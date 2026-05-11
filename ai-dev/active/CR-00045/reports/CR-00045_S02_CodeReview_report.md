# CR-00045 S02 Code Review Report

## Review Summary

Reviewed S01 (backend-impl) implementation of CR-00045 — Require & verify TDD RED-run evidence from the `backend-impl` agent. The implementation is substantively correct across all acceptance criteria, but there is one out-of-scope file change and the `iw sync-agents` command appears to have been re-run after it was already complete, causing the synced copies to diverge from their masters.

---

## Files Changed

Listed by the implementation report:
- `agents/claude/backend-impl.md`
- `agents/opencode/backend-impl.md`
- `.claude/agents/backend-impl.md`
- `.opencode/agents/backend-impl.md`
- `templates/design/Implementation_Prompt_Template.md`
- `ai-dev/templates/Implementation_Prompt_Template.md`
- `templates/design/SelfAssess_Prompt_Template.md`
- `ai-dev/templates/SelfAssess_Prompt_Template.md`
- `templates/design/CodeReview_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Prompt_Template.md`
- `tests/unit/test_tdd_red_evidence_contract.py`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

Additional untracked change detected:
- `.opencode/commands/doc-job.md` — trailing newline removed (out of scope for this CR)

---

## Acceptance Criteria Review

### AC1: backend-impl mandates and records RED evidence ✅

Both `agents/claude/backend-impl.md` and `agents/opencode/backend-impl.md` now contain:
- The explicit "run the new failing test" language in the RED step
- Targeted-run instruction (`uv run pytest tests/.../test_x.py -v`, never full suite)
- Confirm-reason step (`AssertionError`/`NotImplementedError`, not import/collection error)
- Capture failing line(s)
- `tdd_red_evidence` field in the Subagent Result Contract JSON, with both documented forms

The synced copies (`.claude/agents/backend-impl.md`, `.opencode/agents/backend-impl.md`) show the same changes **plus an additional `preflight` block** not present in the masters. See Finding #1.

### AC2: prompt templates reflect the contract ✅

All three template pairs are byte-identical between `templates/design/` and `ai-dev/templates/`:
- `Implementation_Prompt_Template.md` — TDD section expanded, `tdd_red_evidence` in contract JSON
- `SelfAssess_Prompt_Template.md` — TDD RED evidence checklist item present, scoped to behaviour-implementing steps, tests-impl exempt
- `CodeReview_Prompt_Template.md` — section 5a TDD RED Evidence review check with mandatory steps 1–2 and explicitly optional step 3

### AC3: guard test pins the contract and was written RED-first ✅

`tests/unit/test_tdd_red_evidence_contract.py` is a well-structured pure file-content test with 19 parametrized assertions:
- 8 files × `tdd_red_evidence` marker assertion
- 8 files × `run the new failing test` phrase assertion
- 3 template pair byte-identity assertions

The report documents 16 `AssertionError` failures during the RED phase (correct failure mode, not import/syntax/collection error), and 19 passed after GREEN phase. All 19 tests pass on the current run.

### AC4: in-project agent copies are in sync ❌

`iw sync-agents` was run, but the synced copies in `.claude/agents/` and `.opencode/agents/` now **differ** from their masters by an extra `preflight` block. This means the sync command was run **twice** — once correctly after the initial agent edits, and again after the implementation template edits (which also touched the same JSON contract structure), causing the synced copies to absorb changes from the template edits that were never propagated back to the masters.

See Finding #1.

### AC5: the plan is updated ✅

`ai-dev/work/TESTS_ENHANCEMENT.md` item 0.4 shows:
- Status: `**DONE 2026-05-11 (CR-00045)**`
- Link: `CR-00045`
- Changelog entry present at line 188 with full implementation summary

---

## Pre-Flight Lint & Format Gate

| Gate | Command | Result |
|------|---------|--------|
| `make lint` | `uv run ruff check .` | ✅ All checks passed |
| `make format` | `uv run ruff format --check` | ✅ 672 files already formatted |

No new violations introduced by this step.

---

## Test Results

**Guard test** (`tests/unit/test_tdd_red_evidence_contract.py`): **19 passed, 0 failed**

**Full unit suite** (`make test-unit` excluding guard test): **2748 passed, 4 skipped, 5 xfailed, 1 xpassed** — no regressions.

---

## Findings

### Finding #1 — `.opencode/commands/doc-job.md` modified (out of scope)

**Severity:** LOW (informational — no functional impact, no merge risk)
**Category:** `conventions`
**File:** `.opencode/commands/doc-job.md`
**Line:** 16 (end of file)
**Description:** The file has a trailing newline removed (original ended with `\n`, now ends with no newline). This is a 1-character whitespace change. It was not listed in the design's `files_changed`, not in scope for CR-00045, and not introduced by the S01 agent (which did not touch this file). Likely a side effect of the text editor used by the agent or a pre-existing uncommitted change.
**Suggestion:** Run `echo "" >> .opencode/commands/doc-job.md` to restore the trailing newline. This file is outside CR-00045's scope — do not include it in the commit.

---

### Finding #2 — Synced agent copies diverge from masters (AC4 not fully met)

**Severity:** HIGH
**Category:** `conventions`
**File:** `.opencode/agents/backend-impl.md`, `.claude/agents/backend-impl.md`
**Line:** JSON contract block
**Description:** The synced copies (`.opencode/agents/backend-impl.md`, `.claude/agents/backend-impl.md`) contain an additional `preflight: { format, typecheck, lint }` block that is absent from their masters (`agents/opencode/backend-impl.md`, `agents/claude/backend-impl.md`). `git diff agents/opencode/backend-impl.md .opencode/agents/backend-impl.md` shows 20 lines of extra content including the preflight block.

The likely sequence: (a) agent edits the masters and runs `iw sync-agents` — copies are in sync; (b) agent then edits the implementation templates (which also contain a Subagent Result Contract JSON with `preflight` block) and somehow triggers a second `iw sync-agents` run (perhaps as part of post-edit verification), which overwrites the already-correct synced copies with a hybrid version that includes the template's preflight structure.

This violates AC4's requirement that `.opencode/agents/backend-impl.md` and `agents/opencode/backend-impl.md` be identical.

**Suggestion:** Re-run `uv run iw sync-agents` from a clean state (with only the intentional master edits staged). Verify with `git diff agents/opencode/backend-impl.md .opencode/agents/backend-impl.md` and `git diff agents/claude/backend-impl.md .claude/agents/backend-impl.md` that both return empty before committing.

**Note:** This is a fixable issue — a single `iw sync-agents` invocation from the correct state will restore sync. It does not require re-doing the core agent/template edits.

---

## Notes

- **RED-first evidence is properly documented.** The implementation report correctly captures 16 `AssertionError` failures during the RED phase, confirming the guard test was written before any agent/template edits.
- **`iw sync-templates` was correctly omitted.** The implementation report notes this is a post-merge operator step — consistent with the design doc.
- **The `preflight` field in synced copies** likely originated from the `Implementation_Prompt_Template.md` contract block, which already had a `preflight` structure. The backend-impl agent definition itself did not previously have `preflight` — it was added to the agents as part of the same CR-00045 edits, but the sync process pulled in a version that also included the template's `preflight` structure (which predates CR-00045).
- **No migration changes, no Docker state changes.** The CR is purely markdown + one Python test file. This is correct.

---

## Verdict

**fail** — AC4 (in-project agent copies in sync) is not satisfied due to the extra `preflight` block in synced copies. One mandatory fix: re-sync agents from masters.

**mandatory_fix_count:** 1 (HIGH — AC4 violation)
**tests_passed:** true
**test_summary:** 19 passed (guard test) + 2748 passed (full unit suite, no regressions)

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00045",
  "step_reviewed": "S01",
  "verdict": "fail",
  "findings": [
    {
      "severity": "HIGH",
      "category": "conventions",
      "file": ".opencode/agents/backend-impl.md",
      "line": 101,
      "description": "AC4 violation: synced copy differs from master. Contains extra `preflight` block (format/typecheck/lint fields) absent from agents/opencode/backend-impl.md. Same issue in .claude/agents/backend-impl.md. `iw sync-agents` was apparently run a second time after template edits, overwriting correct copies with a hybrid version.",
      "suggestion": "Re-run `uv run iw sync-agents` from a clean state (only the intentional master edits staged). Verify `git diff agents/opencode/backend-impl.md .opencode/agents/backend-impl.md` and `git diff agents/claude/backend-impl.md .claude/agents/backend-impl.md` return empty before committing."
    },
    {
      "severity": "LOW",
      "category": "conventions",
      "file": ".opencode/commands/doc-job.md",
      "line": 16,
      "description": "Trailing newline removed — 1-character whitespace change. Not listed in design's files_changed, not in CR-00045 scope.",
      "suggestion": "Run `echo '' >> .opencode/commands/doc-job.md` to restore the trailing newline. Exclude this file from the CR-00045 commit."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "19 passed (guard test), 2748 passed (full unit suite), 0 failed — no regressions",
  "notes": "AC1, AC2, AC3, AC5 all fully satisfied. AC4 (agent sync) failed due to double sync-agents run. The core agent/template/guard-test implementation is correct and complete."
}
```