# I-00082_S01_Pipeline_prompt

**Work Item**: I-00082 — Fix-cycle agent has no allowed_paths enforcement
**Step**: S01
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

(Standard policy. See `docs/IW_AI_Core_Agent_Constraints.md`. This step
adds no Docker usage.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This step touches no migrations.)

## Input Files

- **Runtime step state**: `uv run iw item-status I-00082 --json`
- `ai-dev/active/I-00082/I-00082_Issue_Design.md` — design document (READ FIRST)
- `orch/daemon/fix_cycle.py` — current fix-cycle implementation
- `executor/scope_gate.py` — existing merge-time scope gate (reuse the matching logic, don't reimplement)
- `executor/worktree_commit.sh` Step 2.25 — calling convention reference
- `orch/daemon/CLAUDE.md` — daemon module conventions

## Output Files

- `ai-dev/work/I-00082/reports/I-00082_S01_Pipeline_report.md` — step report
- Modified: `orch/daemon/fix_cycle.py`

## Context

You are implementing **I-00082 — Fix-cycle agent has no allowed_paths enforcement**.

CR-00053 demonstrated two failure modes that both deadlock the workflow:

1. **Drift mode** — fix-cycle agent edits files outside `scope.allowed_paths`,
   introducing new errors that re-trip the failed gate (S09, fix cycle 3:
   added 5-line-error RAG tests to "fix" a different lint error).
2. **Revert mode** — fix-cycle agent silently reverts operator-applied
   carry-over fixes that happen to be out of scope (S15, fix cycle 2:
   reverted a one-line `BatchStatus.executing → completed` operator fix).

Read the design doc end-to-end before writing code. The full deliverable
list, all 4 acceptance criteria, the reproduction test specification, and
the dependencies on `executor/scope_gate.py` are spelled out there.

## Requirements

### 1. Inject `allowed_paths` into the fix-cycle prompt

Locate the fix-cycle prompt assembly site in `orch/daemon/fix_cycle.py`
(grep for the fix-prompt heredoc / template builder). Before the existing
"Errors to Address" / "Constraints" sections, insert a new section:

```
## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  <one path per line, exactly as in scope.allowed_paths>

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.
```

If `scope.allowed_paths` is empty or missing in the manifest, render
`(none declared — scope enforcement disabled for this item)` and skip the
post-cycle reconciliation in deliverable 2 below.

### 2. Post-cycle scope reconciliation (no auto-revert)

After the fix-cycle agent's subprocess exits, before deciding whether to
re-run the failing gate:

- Compute the working-tree diff against the cycle-start commit:
  `git diff --name-only <cycle_start_sha>` for both staged and unstaged.
- Filter the resulting paths through `scope_gate.py`'s matcher (or the
  equivalent Python helper). Implicit allowances continue to apply:
  `ai-dev/active/I-00082/**`, `ai-dev/archive/I-00082/**`,
  `ai-dev/work/I-00082/**`.
- If any path is **not** allowed, set the cycle outcome to
  `escalate-to-operator` (new outcome — define it alongside the existing
  `pass` / `fail` / `timeout` enum). Record the violation paths in the
  cycle's metadata. **Do NOT git checkout / revert** — keep the agent's
  edits in the working tree exactly as they are. The operator will inspect
  and decide.

If every path is allowed, behaviour is unchanged from today.

### 3. Operator-pre-edit preservation

When a cycle starts, capture the worktree's working-tree diff *before*
launching the agent. After the cycle, the post-cycle reconciliation in
deliverable 2 compares the *new* working-tree diff against the
*pre-cycle* diff. Files that were modified before the cycle started but
that the agent did not touch must NOT count as violations — they were the
operator's edits, not the agent's.

Implementation hint: take a `git stash --keep-index` snapshot at cycle
start that records the pre-cycle path set; after the cycle, the violation
set is `(post_cycle_paths - pre_cycle_paths) - allowed_paths`.

### 4. Daemon log line per cycle

Emit one structured INFO log line per fix cycle:

```
fix_cycle scope: item=I-00082 step=S05 cycle=2 allowed=3 in_scope=2 out_of_scope=1 violations=[orch/cancel.py]
```

Use the existing logger pattern in `orch/daemon/fix_cycle.py`. This makes
stuck-CR triage trivial.

### 5. State machine update

Wherever the fix-cycle outcome is consumed (`orch/daemon/fix_cycle.py`,
possibly `orch/daemon/batch_manager.py`, possibly `orch/daemon/state_machine.py`),
handle the new `escalate-to-operator` outcome:

- Mark the step's status as `needs_fix` (existing terminal-for-daemon state).
- Write a one-line reason: `fix_cycle escalated: agent edited N files outside scope`.
- Record the violation paths into the step's metadata so the dashboard /
  `iw item-status` can display them.
- Do NOT count escalation against the fix-cycle budget (3 / 5 / wherever).
  An escalation is a clean exit, not a failed retry.

## Project Conventions

Read `CLAUDE.md` and `orch/daemon/CLAUDE.md`. Match the existing logging
style in `orch/daemon/fix_cycle.py`. Use the existing manifest-loading
helper (search `manifest` / `scope.allowed_paths` in `orch/`) — do not
re-parse the JSON ad-hoc.

## TDD Requirement

RED first: write the failing reproduction test from the design doc
(`tests/integration/test_fix_cycle_scope_enforcement.py`) and run it to
confirm `AssertionError: expected 'escalate-to-operator' but got 'pass'`
(or equivalent). Capture the failing line in `tdd_red_evidence` before
writing the production code. Then GREEN, then REFACTOR.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — must report no changes (or, if it changed files, re-stage and verify clean).
2. `make type-check` — zero errors involving `orch/daemon/fix_cycle.py`.
3. `make lint` — zero errors.

Populate `preflight` in the result contract.

## Test Verification (NON-NEGOTIABLE)

Run only the test file you authored / modified:

```bash
uv run pytest tests/integration/test_fix_cycle_scope_enforcement.py -v
```

Do NOT run `make test-integration` or `make test-unit` here — those are
S10 / S11 QV gates with their own budgets.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "pipeline-impl",
  "work_item": "I-00082",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/daemon/fix_cycle.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/integration/test_fix_cycle_scope_enforcement.py::test_i00082_fix_cycle_escalates_on_out_of_scope_edit — AssertionError: expected outcome 'escalate-to-operator', got 'pass'",
  "blockers": [],
  "notes": ""
}
```
