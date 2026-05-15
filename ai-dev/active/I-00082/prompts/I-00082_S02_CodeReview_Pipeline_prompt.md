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
  `git restore`, `git stash drop`, or rewrites a file the agent edited
  outside `allowed_paths`. The design forbids auto-revert; the operator
  decides.
- **Operator-pre-edits counted as violations**: the post-cycle
  reconciliation must subtract the pre-cycle path set so an operator's
  carry-over edit is not flagged as the agent's drift.
- **Escalation counted against fix-cycle budget**: an `escalate-to-operator`
  outcome must NOT increment `fix_cycles.cycle_count` toward the 3 / 5
  cap (otherwise we re-introduce the original deadlock).

### HIGH

- Manifest-loading: must reuse existing helper, not re-parse JSON ad-hoc.
- Scope matching: must reuse `executor/scope_gate.py`'s matcher (or its
  Python equivalent in `orch/`), not reimplement glob handling.
- Daemon log line shape: must match the spec exactly so dashboard
  parsing later (out of scope here) has a stable contract:
  `fix_cycle scope: item=<ID> step=<SXX> cycle=<N> allowed=<K> in_scope=<M> out_of_scope=<P> violations=[...]`
- Empty / missing `scope.allowed_paths`: must render the no-enforcement
  branch and skip reconciliation, NOT fail-closed (legacy items must
  continue to work unchanged).

### MEDIUM

- TDD RED evidence in S01 report: must capture the exact failing line
  from running the reproduction test pre-fix.
- Prompt-injection text: should be operator-readable, not LLM-cargo-cult
  filler.
- New `escalate-to-operator` enum value: must be used consistently
  wherever the cycle outcome is consumed.

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
