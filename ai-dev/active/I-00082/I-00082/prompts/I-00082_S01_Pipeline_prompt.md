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
- New: `tests/integration/test_fix_cycle_scope_enforcement.py` — **only** the
  AC1 reproduction test (one `def test_i00082_...` function). S03 will
  extend this file with AC3/AC4 tests.

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

- Build the matcher as an **inline mirror** of `executor/scope_gate.py:_matches()`
  — copy the 4-line function and the implicit-allow construction (`ai-dev/active/<ID>/**`,
  `ai-dev/archive/<ID>/**`, `ai-dev/work/<ID>/**`) into a private helper
  inside `orch/daemon/fix_cycle.py` (e.g. `_scope_match()` and
  `_implicit_allows(item_id)`). Do **NOT** import from `executor/` — that
  script must remain a self-contained CLI. Do **NOT** shell out to
  `python3 scope_gate.py` per cycle — subprocess overhead and double-error
  handling. The duplication is intentional and documented in the design
  doc.
- Run the matcher over the post-cycle working-tree paths captured in
  deliverable 3 below.
- If any post-cycle path falls outside `allowed_paths + implicit_allows`,
  set `FixCycle.status = FixStatus.escalated` (the enum value already
  exists in `orch/db/models.py:165` — **DO NOT introduce a new string
  outcome**; reuse the existing `escalated` value). Record the violation
  paths in `FixCycle.fix_metadata["scope_violations"]`. Emit a
  `DaemonEvent` of type `scope_violation_escalation` mirroring the
  `handle_spec_mismatch_escalation` pattern at the top of the module
  (`orch/daemon/fix_cycle.py:162`).
- **Do NOT git checkout / revert / stash drop** — keep the agent's edits
  in the working tree exactly as they are. The operator will inspect and
  decide.

If every path is allowed, behaviour is unchanged from today.

### 3. Operator-pre-edit preservation (set-diff snapshots)

The pre-cycle / post-cycle reconciliation is a pure path-set diff. **Do
NOT use `git stash`** — stashing would hide operator pre-edits from the
fix-cycle agent (defeating AC3) and risks merge conflicts on restore.

Implementation:

```python
def _captured_paths(worktree: pathlib.Path) -> set[str]:
    # Tracked changes (staged + unstaged) plus untracked files.
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=worktree, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=worktree, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return {p for p in tracked + untracked if p.strip()}

pre_cycle_paths = _captured_paths(worktree)   # before launching the agent
# … run the fix-cycle agent …
post_cycle_paths = _captured_paths(worktree)  # after the agent exits

agent_touched = post_cycle_paths - pre_cycle_paths
violations = [p for p in agent_touched
              if not any(_scope_match(p, pat) for pat in allowed + implicit_allows(item_id))]
```

A file the operator modified before the cycle started but the agent did
NOT touch is in `pre_cycle_paths` AND `post_cycle_paths`; the set
subtraction removes it from `agent_touched`, so it cannot become a
violation. AC3 is satisfied by construction.

### 4. Daemon log line per cycle

Emit one structured INFO log line per fix cycle:

```
fix_cycle scope: item=I-00082 step=S05 cycle=2 allowed=3 in_scope=2 out_of_scope=1 violations=[orch/cancel.py]
```

Use the existing logger pattern in `orch/daemon/fix_cycle.py`. This makes
stuck-CR triage trivial.

### 5. State machine update

Reuse the existing `FixStatus.escalated` value — do **NOT** add a new
enum member, do **NOT** add a new outcome string. The path is:

- Set `FixCycle.status = FixStatus.escalated` and record the violation
  paths in `FixCycle.fix_metadata["scope_violations"] = [...]`.
- Emit a `DaemonEvent` of type `scope_violation_escalation` carrying the
  reason `f"fix_cycle escalated: agent edited {len(violations)} files outside scope"`.
  Mirror the call shape used by `handle_spec_mismatch_escalation` at
  `orch/daemon/fix_cycle.py:162` (same module, same logger pattern).
- Leave the step's status at whatever the gate-failure path set it to
  (typically `failed needs human review`). Operators inspect via
  `iw item-status` and the dashboard.
- Do NOT count an escalation against the fix-cycle budget (3 / 5 /
  wherever). An escalation is a clean exit, not a failed retry — the
  caller that increments the budget must check `status != FixStatus.escalated`
  before bumping.

## Project Conventions

Read `CLAUDE.md` and `orch/daemon/CLAUDE.md`. Match the existing logging
style in `orch/daemon/fix_cycle.py`. Use the existing manifest-loading
helper (search `manifest` / `scope.allowed_paths` in `orch/`) — do not
re-parse the JSON ad-hoc.

## TDD Requirement

RED first: author the reproduction test only —
`tests/integration/test_fix_cycle_scope_enforcement.py::test_i00082_fix_cycle_escalates_on_out_of_scope_edit`
(spelled out in the design doc's "Test to Reproduce" section). Run it
*before* touching `orch/daemon/fix_cycle.py` and capture the failing
assertion line in `tdd_red_evidence` — the assertion will read something
like `AssertionError: expected outcome FixStatus.escalated, got
FixStatus.completed` (or similar — exact message depends on how the test
exposes the cycle status).

Then GREEN (implement deliverables 1-5), then REFACTOR.

**Scope split with S03**: this step owns only the AC1 reproduction test.
S03 (`tests-impl`) extends the same file with AC3 (operator-pre-edit
preservation) and AC4 (in-scope happy path) regression tests on top of
your reproduction test. Do **NOT** author AC3 or AC4 here — leave the
file at one test so S03's diff is clean.

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
  "files_changed": [
    "orch/daemon/fix_cycle.py",
    "tests/integration/test_fix_cycle_scope_enforcement.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "1 passed, 0 failed (AC3/AC4 added in S03)",
  "tdd_red_evidence": "tests/integration/test_fix_cycle_scope_enforcement.py::test_i00082_fix_cycle_escalates_on_out_of_scope_edit — AssertionError: expected FixStatus.escalated, got FixStatus.completed",
  "blockers": [],
  "notes": ""
}
```
