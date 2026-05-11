# CR-00045: Require & verify TDD RED-run evidence from the `backend-impl` agent

**Type**: Change Request
**Priority**: Medium
**Reason**: Enforce TDD that is currently aspirational — close the oracle-problem gap where AI agents write tests *after* the code that merely confirm "what the code does". Item 0.4 of the testing-enhancement plan (`ai-dev/work/TESTS_ENHANCEMENT.md`), the final Phase-0 item.
**Created**: 2026-05-11
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy applies. This CR touches no Docker/compose state. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. **This CR adds no migration and modifies none** — it changes agent/prompt-template markdown and adds one pure-content unit test. No `orch/db/migrations/versions/**` changes.

## Description

The `backend-impl` agent already instructs itself to follow TDD ("RED, GREEN, REFACTOR"), but nothing requires it to *actually run* the new failing test before writing the implementation, nothing requires it to confirm the failure is for the right reason, and nothing records that the test was RED. The Subagent Result Contract has `tests_passed` (all-green at the end) but no field proving the tests failed first. This CR makes RED-run evidence a **required, recorded, and lightly-verified** artifact: `backend-impl` must run the new test(s), confirm they fail with an assertion / `NotImplementedError` (not an import/collection error), and record a `tdd_red_evidence` field in its result JSON; the Implementation / SelfAssess / CodeReview prompt templates gain matching language; and a small guard test pins the contract strings in place.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant standards introduced earlier in this initiative: `docs/IW_AI_Core_Testing_Strategy.md` §6 (TDD & RED evidence) and `skills/iw-ai-core-testing/SKILL.md` §5 (record-the-RED). Agent definition masters live under `agents/claude/` and `agents/opencode/`, synced to `.claude/agents/` and `.opencode/agents/` via `iw sync-agents`. Prompt-template masters live under `templates/design/`, with iw-ai-core's own working copies under `ai-dev/templates/`, propagated to other managed projects via `iw sync-templates`.

## Current Behavior

- `agents/claude/backend-impl.md` and `agents/opencode/backend-impl.md`: the "Required Workflow" section says *"Apply TDD (RED, GREEN, REFACTOR): RED: Write failing tests first…"* and the Subagent Result Contract JSON contains `step`, `agent`, `work_item`, `completion_status`, `files_changed`, `tests_passed`, `test_summary`, `blockers`, `notes`. There is **no instruction to run the failing test, no check on the failure reason, and no `tdd_red_evidence` field**.
- `ai-dev/templates/Implementation_Prompt_Template.md` (+ `templates/design/` master): has a "TDD Requirement" section ("Do not skip the RED phase. Tests must exist before implementation code.") and a "Test Verification" section that tells implementation steps to run only *targeted* tests. The Subagent Result Contract block lists `preflight`, `tests_passed`, `test_summary` but **no `tdd_red_evidence`**.
- `ai-dev/templates/SelfAssess_Prompt_Template.md` (+ master): no checklist item about RED evidence.
- `ai-dev/templates/CodeReview_Prompt_Template.md` (+ master): no review check about RED evidence.
- There is no test asserting any of these contract strings exist (precedent for such tests: `tests/unit/test_template_hints.py`, added by CR-00023).

## Desired Behavior

- **`backend-impl` agent (both mirrors)** — the TDD step is explicit and mandatory: (1) write the failing behavioural test(s); (2) **run them** (targeted run only — `uv run pytest tests/.../test_x.py -v`, never the full suite); (3) **confirm the failure is for the expected reason** — an `AssertionError` or `NotImplementedError` / `AttributeError` from missing-implementation, *not* an `ImportError`, `SyntaxError`, `fixture error`, or collection error (those mean the test itself is broken, not RED); (4) capture the failing line(s). The Subagent Result Contract gains a `tdd_red_evidence` field:
  - When the step adds behavioural test(s): a short string/array — the test id(s) plus a 1–3 line snippet of the RED run output (the failure line), e.g. `"tests/unit/test_x.py::test_foo — AssertionError: assert 0 == 42"`.
  - When the step legitimately adds no behavioural test (pure refactor, config-only, doc/template-only): `"n/a — <one-line reason>"`, e.g. `"n/a — template/markdown edits only, no production logic"`.
  - `tests_passed` / `test_summary` keep their meaning (final all-green state of the targeted tests).
- **`Implementation_Prompt_Template.md` (+ master)** — the "TDD Requirement" section spells out the run-and-confirm-reason step; the Subagent Result Contract block adds `"tdd_red_evidence": "..."`. The wording makes clear it is required for Backend steps; for non-behavioural steps the `"n/a — …"` form is expected. It does not bloat non-backend prompts (the field is in the shared contract block; the prose explains when `"n/a"` applies).
- **`SelfAssess_Prompt_Template.md` (+ master)** — a checklist item: *"If the reviewed step(s) added behavioural tests, the step report contains `tdd_red_evidence` with a plausible RED failure snippet (`AssertionError` / `NotImplementedError`, not an import/collection error). If it added none, the report says so with a one-line justification."*
- **`CodeReview_Prompt_Template.md` (+ master)** — a review check: the reviewer (1) confirms `tdd_red_evidence` is present and plausible for any new behavioural tests; (2) for at least one new behavioural test, **reasons about whether it would actually fail against the pre-change production code** and flags any that obviously would not (a test that passes without the new code is not a RED-first test); (3) *may optionally*, when quick and safe, scope-stash only the production-code hunks for that test's target, re-run the test to see it fail, and restore — but the stash-recheck is **optional**, not mandatory, because a `git stash` mid-workflow in the worktree is risky. The mandatory part is steps (1) and (2).
- **Guard test** — `tests/unit/test_tdd_red_evidence_contract.py`: pure file-content assertions that `agents/claude/backend-impl.md`, `agents/opencode/backend-impl.md`, `templates/design/Implementation_Prompt_Template.md`, `ai-dev/templates/Implementation_Prompt_Template.md`, `templates/design/SelfAssess_Prompt_Template.md`, `ai-dev/templates/SelfAssess_Prompt_Template.md`, `templates/design/CodeReview_Prompt_Template.md`, and `ai-dev/templates/CodeReview_Prompt_Template.md` each contain the key marker strings (`tdd_red_evidence`, and a short phrase from the mandatory-RED language). This makes the contract a regression-tested invariant and gives this CR a real test to write RED-first (the test fails until the edits land).
- **`iw sync-agents`** is run so `.claude/agents/backend-impl.md` and `.opencode/agents/backend-impl.md` reflect the master edits.
- Item 0.4 in `ai-dev/work/TESTS_ENHANCEMENT.md` is ticked DONE and its changelog updated.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `agents/claude/backend-impl.md` (+ `.claude/agents/backend-impl.md` via sync) | TDD step says "write failing tests first"; result JSON has no RED field | TDD step mandates run + confirm-reason + capture; result JSON gains `tdd_red_evidence` |
| `agents/opencode/backend-impl.md` (+ `.opencode/agents/backend-impl.md` via sync) | same as above | same as above |
| `templates/design/Implementation_Prompt_Template.md` + `ai-dev/templates/Implementation_Prompt_Template.md` | "TDD Requirement" section; result-contract block without RED field | run-and-confirm-reason wording; result-contract block gains `tdd_red_evidence` |
| `templates/design/SelfAssess_Prompt_Template.md` + `ai-dev/templates/SelfAssess_Prompt_Template.md` | no RED-evidence checklist item | adds the checklist item |
| `templates/design/CodeReview_Prompt_Template.md` + `ai-dev/templates/CodeReview_Prompt_Template.md` | no RED-evidence review check | adds the review check (mandatory reason-check + optional stash-recheck) |
| `tests/unit/test_tdd_red_evidence_contract.py` | does not exist | new — content-assertion guard test |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | item 0.4 = TODO | item 0.4 = DONE + changelog entry |

### Breaking Changes

- **None.** `tdd_red_evidence` is an additive field; the orchestrator parses the Subagent Result Contract leniently (extra/missing keys do not break parsing — existing reports without the field continue to work). The SelfAssess and CodeReview template additions are additive checklist/check items. The `code-review-fix-impl` / `code-review-fix-final-impl` and QV-gate fix cycles are unaffected. No workflow-manifest schema change.

### Data Migration

- **None.** No database changes. Reversible by `git revert` of the merge commit (re-run `iw sync-agents` afterward to regenerate the in-project agent copies).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | RED-first: write `tests/unit/test_tdd_red_evidence_contract.py` (it fails); then edit the two `agents/.../backend-impl.md` masters, the three `templates/design/*.md` masters + their three `ai-dev/templates/*.md` copies; run `iw sync-agents`; tick item 0.4 in `ai-dev/work/TESTS_ENHANCEMENT.md`. Record `tdd_red_evidence` for the new guard test in the result JSON (eating its own dogfood). | — |
| S02 | `code-review-impl` | Review S01: are the agent/template edits consistent across all 8 files, does the guard test actually assert the right strings, does the result-JSON example include `tdd_red_evidence`, was `iw sync-agents` run (diff `.claude/agents/backend-impl.md` vs `agents/claude/backend-impl.md`), is item 0.4 ticked? | — |
| S03 | `code-review-final-impl` | Global review: the agent ↔ template ↔ guard-test chain is internally consistent and the new contract is unambiguous; no out-of-scope edits; the optional-vs-mandatory split in the CodeReview template is stated clearly. | — |
| S04 | `qv-gate` (`lint`) | `make lint` | — |
| S05 | `qv-gate` (`format`) | `make format-check` | — |
| S06 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S07 | `qv-gate` (`unit-tests`) | `make test-unit` | — |
| S08 | `qv-gate` (`integration-tests`) | `make allure-integration` (timeout 900) | — |
| S09 | `self-assess-impl` | Self-assessment via the `iw-item-analyze` skill (project has `self_assess = true`). | — |

Agent slugs: `backend-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`. Fix cycles (`code-review-fix-impl`, `code-review-fix-final-impl`, QV-gate fixes) are dynamic and not listed in the manifest.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — this CR adds/modifies no Alembic migration, so no `migration-check` gate is needed.

### API Changes

- **New endpoints**: None · **Modified endpoints**: None · **Removed endpoints**: None

### Frontend Changes

- **New components**: None · **Modified components**: None · **Removed components**: None — `browser_verification: false`.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/CR-00045/CR-00045_CR_Design.md` | Design | This document |
| `ai-dev/active/CR-00045/CR-00045_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `ai-dev/active/CR-00045/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/CR-00045/prompts/CR-00045_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `ai-dev/active/CR-00045/prompts/CR-00045_S02_CodeReview_prompt.md` | Prompt | S02 review instructions |
| `ai-dev/active/CR-00045/prompts/CR-00045_S03_CodeReview_Final_prompt.md` | Prompt | S03 final review instructions |
| `ai-dev/active/CR-00045/prompts/CR-00045_S09_SelfAssess_prompt.md` | Prompt | S09 self-assessment instructions |

Files **changed** by the implementation (mirrored to `workflow-manifest.json:scope.allowed_paths`):
`agents/claude/backend-impl.md`, `agents/opencode/backend-impl.md`, `.claude/agents/backend-impl.md`, `.opencode/agents/backend-impl.md`, `templates/design/Implementation_Prompt_Template.md`, `templates/design/SelfAssess_Prompt_Template.md`, `templates/design/CodeReview_Prompt_Template.md`, `ai-dev/templates/Implementation_Prompt_Template.md`, `ai-dev/templates/SelfAssess_Prompt_Template.md`, `ai-dev/templates/CodeReview_Prompt_Template.md`, `tests/unit/test_tdd_red_evidence_contract.py`, `ai-dev/work/TESTS_ENHANCEMENT.md`.

Reports are created during execution in `ai-dev/work/CR-00045/reports/`.

## Acceptance Criteria

### AC1: backend-impl mandates and records RED evidence

```
Given the backend-impl agent definition (both agents/claude/backend-impl.md and agents/opencode/backend-impl.md, and the synced .claude/agents/ and .opencode/agents/ copies)
When you read its "Required Workflow" TDD step and its Subagent Result Contract
Then the TDD step requires running the new failing test(s) (targeted run only), confirming the failure is an AssertionError/NotImplementedError-class failure (not an import/collection error), and capturing the failing line(s)
And the Subagent Result Contract JSON includes a "tdd_red_evidence" field with the documented two forms (snippet for behavioural tests; "n/a — <reason>" otherwise)
```

### AC2: prompt templates reflect the contract

```
Given templates/design/Implementation_Prompt_Template.md, templates/design/SelfAssess_Prompt_Template.md, templates/design/CodeReview_Prompt_Template.md and their ai-dev/templates/ copies
When you read the TDD/Requirement, self-assessment checklist, and code-review checklist sections respectively
Then the Implementation template's TDD section describes the run-and-confirm-reason step and its result-contract block includes "tdd_red_evidence"
And the SelfAssess template has a checklist item about the presence/plausibility of tdd_red_evidence
And the CodeReview template has a review check that mandates confirming tdd_red_evidence is present + reasoning about whether each new test would fail against pre-change code, with the stash-recheck explicitly marked optional
And each templates/design/X.md is byte-identical (modulo nothing) to its ai-dev/templates/X.md counterpart
```

### AC3: guard test pins the contract and was written RED-first

```
Given tests/unit/test_tdd_red_evidence_contract.py
When `make test-unit` runs
Then it passes
And the S01 step report's tdd_red_evidence field shows this test failing before the agent/template edits were made (RED-first evidence)
```

### AC4: in-project agent copies are in sync

```
Given the implementation edited agents/claude/backend-impl.md and agents/opencode/backend-impl.md and ran `iw sync-agents`
When you diff .claude/agents/backend-impl.md against agents/claude/backend-impl.md and .opencode/agents/backend-impl.md against agents/opencode/backend-impl.md
Then there is no difference (the synced copies reflect the master edits)
```

### AC5: the plan is updated

```
Given ai-dev/work/TESTS_ENHANCEMENT.md
When you read the Phase 0 table and the changelog
Then item 0.4's status is DONE (with this CR's id) and the changelog has an entry for it
```

## Rollback Plan

- **Database**: Not applicable — no schema or data changes.
- **Code**: `git revert` the squash-merge commit. Then run `iw sync-agents` to regenerate `.claude/agents/backend-impl.md` and `.opencode/agents/backend-impl.md` from the reverted masters. If `iw sync-templates` had already been run post-merge, re-run it (or manually restore the prior template content) in the downstream projects.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: None (Phase 0 items 0.1/0.2/0.3 — the testing strategy doc, the `iw-ai-core-testing` skill, the `tests/CLAUDE.md` updates — are already merged; this CR references but does not require changes to them).
- **Blocks**: Nothing hard. Conceptually it's the closeout of Phase 0; Phase 1 items can proceed independently.

## Impacted Paths

- `agents/claude/backend-impl.md`
- `agents/opencode/backend-impl.md`
- `.claude/agents/backend-impl.md`
- `.opencode/agents/backend-impl.md`
- `templates/design/Implementation_Prompt_Template.md`
- `templates/design/SelfAssess_Prompt_Template.md`
- `templates/design/CodeReview_Prompt_Template.md`
- `ai-dev/templates/Implementation_Prompt_Template.md`
- `ai-dev/templates/SelfAssess_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Prompt_Template.md`
- `tests/unit/test_tdd_red_evidence_contract.py`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

- **Unit tests**: `tests/unit/test_tdd_red_evidence_contract.py` — content assertions over the 8 agent/template files (each contains `tdd_red_evidence` and a phrase from the mandatory-RED language). This is the RED-first anchor: the test fails before the edits, passes after. Optionally extend `tests/unit/test_template_hints.py` instead of a new file if the implementer prefers consistency — but a dedicated file is cleaner. No mocks, no DB, no I/O concerns (it just reads repo files).
- **Integration tests**: None needed — there is no runtime behaviour to integration-test (the change is to agent/prompt markdown consumed by the orchestrator at workflow-build time, which is exercised end-to-end by future work items, not by this CR).
- **Updated tests**: None — no existing test asserts on these contract strings yet.

## Notes

- **Why `backend-impl` is the implementation agent**: the change is markdown (agent definitions + prompt templates) plus one small content-assertion test. There is no perfect agent for "edit the agent/prompt files" (`template-impl` is for document-generation/rendering systems, not workflow prompts; `tests-impl` only writes tests). `backend-impl` is the general implementation agent, follows project conventions, and — fittingly — gets to demonstrate the very RED-first flow this CR mandates by writing the guard test first.
- **`make allure-integration` for the integration gate**: this follows the canonical QV-gate set in `skills/iw-workflow/SKILL.md`. Note that `allure-integration` is currently a `.PHONY` target with no recipe (it is a stale stub — see testing-enhancement plan item 1.8, "Allure reporting `make` targets"), so this gate is effectively a no-op for now. The unit-tests gate (`make test-unit`) does run, and includes the new guard test; and the merge-queue dry-run runs the full suite. Fixing the `allure-*` targets is out of scope for this CR (it is plan item 1.8).
- **Cross-repo template propagation is a post-merge operator step, not part of the worktree run.** The implementation edits iw-ai-core's own masters and copies (`templates/design/` + `ai-dev/templates/` + `agents/` + the `iw sync-agents`-regenerated `.claude/`/`.opencode/` copies) — all within the iw-ai-core repo/worktree. After the CR merges, the operator runs `iw sync-templates` (and, if any skill had changed, `iw sync-skills`) to propagate the template changes to the other managed projects (`iw-doc-plan`/InnoForge, `podforger`, `cv`). The worktree must **not** run `iw sync-templates` (it would push the not-yet-merged version into other repos). The `backend-impl` agent should note this in its report rather than do it.
- **Scope discipline**: do not touch `tests-impl`, `database-impl`, `api-impl`, `frontend-impl`, `pipeline-impl`, or `template-impl` agent definitions. If those share a TDD section with `backend-impl`, leave them alone — the RED-evidence *requirement* is for `backend-impl` only. Do not add dependencies (no `mutmut` — mutation testing is plan item 2.1). Do not change the workflow-manifest schema.
- **`tdd_red_evidence` placement in the JSON**: put it adjacent to `tests_passed` / `test_summary` in the contract block (it is part of the same "test outcome" cluster). Keep the example values short so the contract block stays readable.
