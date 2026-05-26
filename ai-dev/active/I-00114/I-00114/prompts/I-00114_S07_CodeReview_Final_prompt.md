# I-00114_S07_CodeReview_Final_prompt

**Work Item**: I-00114 -- pi narration-exit escapes step-done contract, burns retry budget
**Review Step**: S07 — Cross-step global review

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps/inspect/logs` allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. Verify zero migration files were added across all steps. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00114 --json` — runtime step state.
- `ai-dev/active/I-00114/I-00114_Issue_Design.md` — design document.
- `ai-dev/active/I-00114/I-00114_Functional.md` — functional summary.
- All step reports under `ai-dev/active/I-00114/reports/I-00114_S0{1..6}_*_report.md`.
- All files in those reports' `files_changed`.
- Per-agent review reports from S05 and S06 (CRITICAL/HIGH findings must be confirmed fixed or pinned).

## Output Files

- `ai-dev/active/I-00114/reports/I-00114_S07_CodeReview_Final_report.md`

## Context

You are doing the final cross-step global review for I-00114. The per-agent reviews (S05, S06) checked each step in isolation. Your job is to check **integration** — that the CLI (S01), guard (S02), daemon command builders (S03), and tests (S04) actually agree end-to-end and that the work as a whole satisfies AC1..AC5 with no orphans or contradictions.

## Read the Design Document FIRST

Read every Acceptance Criterion (AC1..AC5). Each is a global invariant; verify it's satisfied across the full diff, not just within one step's files.

## Cross-Step Invariants to Verify

### I1. Guard invocation contract — three-way agreement

The guard's CLI surface (S02) and the daemon's invocation (S03) must agree on:

- Flag names: `--item-id`, `--step-id`, `--max-reprompts`, `--`.
- Argument order.
- Whether `max-reprompts` is positional or flagged (and whether the default lives in the guard or in the daemon).

The tests (S04) must invoke the guard with the same surface. Any mismatch → CRITICAL.

### I2. `iw daemon-event` contract — two-way agreement

The CLI added by S01 and the guard's emission code in S02 must agree on:

- Flag names: `--event-type`, `--entity-type`, `--entity-id`, `--message`, `--metadata`.
- The exact value `step_narration_exit` for `event_type` (S04 tests assert on this exact string).
- Metadata schema: `{step_id, reprompt_attempt, max_reprompts, last_assistant_text, verdict}`.

Any drift → CRITICAL.

### I3. pi-only scope

Grep the full diff for any change to:
- `if cli_tool == "opencode"` branches in `_build_initial_command` and `_build_fix_inner_command`.
- `if cli_tool == "claude"` branches in either builder.

Both branches must be byte-identical to pre-fix. Any change → CRITICAL.

### I4. Retry-budget invariant

Verify by reading the diff:

- The guard NEVER calls `iw step-fail` and NEVER calls `iw step-done` itself.
- The guard never directly modifies `step_runs` or `workflow_steps` rows.
- On the 5th reprompt failure, the guard exits with the original pi code (typically 0), letting `_check_step_health → _handle_crashed` fire exactly once. The daemon's existing `should_retry_step` then consumes one retry slot — same as today, exactly **one** slot, not five.

If the guard short-circuits by calling `iw step-fail` after the 5th attempt, that is HIGH because it changes the operator-visible failure classification.

### I5. No migration sneaking

```bash
git diff --name-only main...HEAD -- 'orch/db/migrations/versions/*'
```

Must return zero files. Any migration added → CRITICAL.

### I6. Scope-allowed-paths discipline

`workflow-manifest.json:scope.allowed_paths` lists exactly the files the fix is permitted to touch. Confirm `git diff --name-only main...HEAD` is a subset of:

```
allowed_paths ∪ ai-dev/active/I-00114/** ∪ ai-dev/archive/I-00114/** ∪ ai-dev/work/I-00114/**
```

Anything outside → CRITICAL (and likely indicates a scope miss in the design).

### I7. Functional doc consistency

The functional doc (`I-00114_Functional.md`) makes user-facing claims:

- "Steps that previously stalled are now recovered automatically, without consuming the retry budget."
- "Operators see a new event in the Jobs view labelled 'narration exit'."
- "five nudges" cap.

Confirm each claim is actually delivered by the diff. Mismatch → HIGH.

### I8. No live-DB connection in tests

Per `tests/CLAUDE.md`: scan every new test file for any module-level import of `orch.db.session` (or equivalent) that would connect on import. The testcontainer fixture is the only acceptable DB binding. Violation → CRITICAL.

### I9. Per-agent review findings are resolved

Read S05 and S06's review reports. Every CRITICAL and HIGH finding must either:
- Be marked resolved in the latest fix-cycle (verify by re-checking the cited file/line), OR
- Be explicitly pinned in S07's notes with a justification.

Unresolved + unpinned CRITICALs → BLOCKED verdict.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
make type-check
```

Run against the full I-00114 diff. Any NEW violations → CRITICAL.

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00114",
  "verdict": "PASS|NEEDS_FIX|BLOCKED",
  "ac_status": {
    "AC1": "satisfied|violated|partial",
    "AC2": "satisfied|violated|partial",
    "AC3": "satisfied|violated|partial",
    "AC4": "satisfied|violated|partial",
    "AC5": "satisfied|violated|partial"
  },
  "invariant_status": {
    "I1_guard_contract": "ok|violated",
    "I2_daemon_event_contract": "ok|violated",
    "I3_pi_only_scope": "ok|violated",
    "I4_retry_budget": "ok|violated",
    "I5_no_migrations": "ok|violated",
    "I6_scope_allowed_paths": "ok|violated",
    "I7_functional_doc": "ok|violated",
    "I8_no_live_db": "ok|violated",
    "I9_findings_resolved": "ok|violated"
  },
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "category": "integration|invariant|conventions|correctness",
      "file": "path/to/file",
      "line": 42,
      "description": "Specific issue and suggested fix.",
      "ac_or_invariant_violated": "AC4 / I3"
    }
  ],
  "notes": ""
}
```
