# I-00082_S02_CodeReview_Pipeline_prompt

**Work Item**: I-00082 — Fix-cycle agent has no allowed_paths enforcement
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migration impact.)

## Input Files

- `ai-dev/active/I-00082/I-00082_Issue_Design.md`
- `ai-dev/work/I-00082/reports/I-00082_S01_Pipeline_report.md`
- The S01 diff: `git diff` against the cycle-start commit, focused on `orch/daemon/fix_cycle.py`

## Output Files

- `ai-dev/work/I-00082/reports/I-00082_S02_CodeReview_report.md`

## Context

Per-agent review of S01. The design doc has 4 acceptance criteria; verify
each one is satisfied by the S01 implementation.

## Review Checklist

Group findings by severity (CRITICAL / HIGH / MEDIUM / LOW). For each
finding give: file:line, the rule violated, the evidence, the suggested
fix.

### CRITICAL — must-fix before S03

- **Auto-revert detected**: any code path that runs `git checkout`,
  `git restore`, `git stash`, or rewrites a file the agent edited
  outside `allowed_paths`. The design forbids auto-revert; the operator
  decides. The pre/post-cycle path-set snapshots must use
  `git diff --name-only HEAD` + `git ls-files --others --exclude-standard`
  only — **never** `git stash --keep-index` or similar (which would hide
  operator pre-edits from the agent and defeat AC3).
- **Operator-pre-edits counted as violations**: the post-cycle
  reconciliation must subtract the pre-cycle path set so an operator's
  carry-over edit is not flagged as the agent's drift.
- **New outcome enum invented**: the implementation MUST reuse the
  existing `FixStatus.escalated` value at `orch/db/models.py:165`.
  **Flag CRITICAL** if a new string like `escalate-to-operator` is
  introduced anywhere (enum, string literal, JSON field, log line).
- **Escalation counted against fix-cycle budget**: a cycle with
  `FixCycle.status == FixStatus.escalated` must NOT increment
  `fix_cycles.cycle_count` toward the 3 / 5 cap (otherwise we
  re-introduce the original deadlock).
- **`DaemonEvent` emission missing**: on violation, the daemon MUST emit
  a `DaemonEvent` of type `scope_violation_escalation` mirroring the
  shape of `handle_spec_mismatch_escalation`
  (`orch/daemon/fix_cycle.py:162`). Without this the dashboard cannot
  surface the escalation.

### HIGH

- Manifest-loading: must reuse existing helper, not re-parse JSON ad-hoc.
- Scope matching: must inline-mirror `executor/scope_gate.py:_matches()`
  inside `orch/daemon/fix_cycle.py` (4-line copy). Do NOT import from
  `executor/` (script must stay self-contained); do NOT subprocess-call
  `scope_gate.py` per cycle. Implicit-allow list must include
  `ai-dev/active/<ID>/**`, `ai-dev/archive/<ID>/**`, AND
  `ai-dev/work/<ID>/**` (the merge-time gate only has the first two —
  the fix-cycle adds `work/` because that's where step reports land).
- Daemon log line shape: must match the spec exactly so dashboard
  parsing later (out of scope here) has a stable contract:
  `fix_cycle scope: item=<ID> step=<SXX> cycle=<N> allowed=<K> in_scope=<M> out_of_scope=<P> violations=[...]`
- Empty / missing `scope.allowed_paths`: must render the no-enforcement
  branch and skip reconciliation, NOT fail-closed (legacy items must
  continue to work unchanged).

### MEDIUM

- TDD RED evidence in S01 report: must capture the exact failing line
  from running the reproduction test pre-fix (the assertion will reference
  `FixStatus.escalated` vs. whatever the pre-fix path returned, typically
  `FixStatus.completed`).
- Prompt-injection text: should be operator-readable, not LLM-cargo-cult
  filler.
- `FixStatus.escalated` is used consistently wherever the cycle outcome
  is consumed (no orphan checks against the wrong value).
- S03 ownership: S01 must leave the test file with exactly one test
  (`test_i00082_fix_cycle_escalates_on_out_of_scope_edit`); AC3/AC4 are
  S03's responsibility. Flag MEDIUM if S01 over-reaches.

### LOW

- Naming: `_compute_violations(...)` or similar pure helper extracted for
  unit testing.
- Docstring on the new function citing I-00082 and the two failure modes.

## Verdict

End the report with one of:

- `verdict: pass` — no CRITICAL or HIGH findings; approve for S03
- `verdict: needs-fix` — list the CRITICAL/HIGH findings to address; the
  daemon will spawn a fix cycle

## Subagent Result Contract

Standard `code-review-impl` JSON. Findings grouped by severity. No new
production code in this step.
