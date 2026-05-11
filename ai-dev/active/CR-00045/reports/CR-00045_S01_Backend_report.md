# CR-00045 S01 Backend Report

## What was done

Implemented CR-00045 — Require & verify TDD RED-run evidence from the `backend-impl` agent — in a single backend-impl step.

### Deliverable 1 — RED (guard test written first, confirmed failing)

Created `tests/unit/test_tdd_red_evidence_contract.py`: pure file-content assertions (no DB, no I/O). The test asserts that all 8 in-scope files contain the literal marker `tdd_red_evidence` AND the phrase `run the new failing test` (the mandatory-RED run step), plus that the three template pairs are byte-identical.

**RED run** (before any agent/template edits):
```
FAILED tests/unit/test_tdd_red_evidence_contract.py::test_file_contains_tdd_red_evidence_marker[agents/claude/backend-impl.md]
AssertionError: agents/claude/backend-impl.md: missing 'tdd_red_evidence' contract marker
... (16 failures total — 8 marker + 8 phrase failures, all AssertionError)
```

All failures were `AssertionError` — the correct failure mode, not `ImportError`/`SyntaxError`/collection error.

### Deliverable 2 — Agent definitions (`agents/claude/backend-impl.md` + `agents/opencode/backend-impl.md`)

Edited both files identically. The TDD RED step now reads:
- **(a)** write the failing behavioural test(s);
- **(b)** `run the new failing test` — a *targeted* run only (`uv run pytest tests/.../test_x.py -v`), never the full suite;
- **(c)** confirm the failure is for the expected reason — `AssertionError` or `NotImplementedError`/`AttributeError` from missing-implementation, *not* an import/collection error;
- **(d)** capture the failing line(s).

Added `"tdd_red_evidence": "tests/unit/test_x.py::test_foo — AssertionError: assert 0 == 42  // captured RED run"` to the Subagent Result Contract JSON, with a note explaining the two forms (snippet for behavioural tests, `"n/a — <reason>"` otherwise).

### Deliverable 3 — Implementation templates (`templates/design/` + `ai-dev/templates/`)

Edited `Implementation_Prompt_Template.md` in both locations identically:
- TDD Requirement section: expanded the RED step to match the agent definition wording (run targeted, confirm reason, capture).
- Subagent Result Contract block: added `"tdd_red_evidence"` field with note explaining it is required for Backend steps and the `"n/a — …"` form applies for non-behavioural steps.

### Deliverable 4 — SelfAssess templates (`templates/design/` + `ai-dev/templates/`)

Edited `SelfAssess_Prompt_Template.md` in both locations identically. Added a "TDD RED Evidence (behaviour-implementing steps only)" section with a checklist item scoped to behaviour-implementing steps, noting tests-impl is exempt. The phrase `run the new failing test` appears in the checklist description.

### Deliverable 5 — CodeReview templates (`templates/design/` + `ai-dev/templates/`)

Edited `CodeReview_Prompt_Template.md` in both locations identically. Added section "5a. TDD RED Evidence (behaviour-implementing steps only)" with three steps: (1) confirm `tdd_red_evidence` present and plausible (must contain `run the new failing test`); (2) reason about whether the test would actually fail against pre-change code — flag as HIGH if it would not; (3) optional stash-recheck, explicitly marked optional. The mandatory parts are steps 1 and 2.

### Deliverable 6 — `iw sync-agents`

Ran `uv run iw sync-agents`. Verified with `git diff` that `.claude/agents/backend-impl.md` matches `agents/claude/backend-impl.md` and `.opencode/agents/backend-impl.md` matches `agents/opencode/backend-impl.md` — no remaining diff.

**Did NOT run `iw sync-templates`** — that propagates to other managed projects' repos and is a post-merge operator step, not a worktree step.

### Deliverable 7 — GREEN + plan update

Re-ran `uv run pytest tests/unit/test_tdd_red_evidence_contract.py -v` — **19 passed, 0 failed**. Ticked item 0.4 DONE in `ai-dev/work/TESTS_ENHANCEMENT.md` (Status: `**DONE 2026-05-11 (CR-00045)**`, Link: `CR-00045`) and appended a changelog entry.

## Files changed

| File | Change |
|------|--------|
| `agents/claude/backend-impl.md` | TDD step made explicit; `tdd_red_evidence` added to result contract |
| `agents/opencode/backend-impl.md` | Same edits as claude mirror |
| `templates/design/Implementation_Prompt_Template.md` | TDD step wording + `tdd_red_evidence` in contract JSON |
| `ai-dev/templates/Implementation_Prompt_Template.md` | Same edits as master |
| `templates/design/SelfAssess_Prompt_Template.md` | TDD RED evidence checklist section |
| `ai-dev/templates/SelfAssess_Prompt_Template.md` | Same edits as master |
| `templates/design/CodeReview_Prompt_Template.md` | Section 5a TDD RED Evidence review check |
| `ai-dev/templates/CodeReview_Prompt_Template.md` | Same edits as master |
| `.claude/agents/backend-impl.md` | Synced from master via `iw sync-agents` |
| `.opencode/agents/backend-impl.md` | Synced from master via `iw sync-agents` |
| `tests/unit/test_tdd_red_evidence_contract.py` | New guard test — written RED-first |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Item 0.4 ticked DONE + changelog entry |

## Pre-flight results

| Gate | Result |
|------|--------|
| `make format` | `fixed` — `ruff format` auto-fixed the new test file (trailing commas in parametrization) |
| `make typecheck` | `ok` — zero errors in touched files |
| `make lint` | `ok` — PT006 fix (tuple in parametrize for two-string arg) |

## Test results

**Guard test** (`tests/unit/test_tdd_red_evidence_contract.py`): **19 passed, 0 failed**

RED phase captured: 16 `AssertionError` failures (8 files × 2 assertions — `tdd_red_evidence` marker + `run the new failing test` phrase absent).
GREEN phase: all 19 pass after deliverables 2–7.

## Notes

- `iw sync-agents` was run (regenerated `.claude/agents/backend-impl.md` + `.opencode/agents/backend-impl.md`). `iw sync-templates` was **not** run — that propagates to other managed projects (`iw-doc-plan`/InnoForge, `podforger`, `cv`) and must happen post-merge by the operator, not from this worktree.
- No migration changes — this CR adds/modifies no Alembic migration.
- No Docker state changed.
- The guard test's parametrization fixed a PT006 lint violation (tuple form for two-parameter parametrize).
- Phase 0 of the testing-enhancement plan is now complete (all items 0.1–0.4 done).