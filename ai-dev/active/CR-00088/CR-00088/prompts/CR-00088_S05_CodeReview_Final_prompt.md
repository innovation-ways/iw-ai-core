# CR-00088_S05_CodeReview_Final_prompt

**Work Item**: CR-00088 -- Auto-merge — partial-allowlist semantics in Phase 1 dry-run
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03 (and S04's per-agent review)

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migrations in this CR.)

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00088 --json`
- `ai-dev/active/CR-00088/CR-00088_CR_Design.md` (READ AC1–AC5 in full)
- `ai-dev/active/CR-00088/CR-00088_Functional.md`
- All impl reports: `ai-dev/work/CR-00088/reports/CR-00088_S0{1,2,3}_*_report.md`
- Per-agent review: `ai-dev/work/CR-00088/reports/CR-00088_S04_CodeReview_report.md`
- All files in the union of impl reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00088/reports/CR-00088_S05_CodeReviewFinal_report.md`

## Context

This is the final cross-step review. S04 reviewed S01–S03 in one pass; your job is to catch issues that span steps and verify the AC list end-to-end. The dominant cross-cutting concern is **partition invariants**: refuse-list precedence, order preservation, and Phase-1 worktree non-mutation. Verify they hold across every layer (classifier ⇄ event emission ⇄ integration test).

## Read the Design Document FIRST

Read AC1–AC6 in full. For each AC, record `PASS` or `FAIL` with the evidence (file + line or command output) that justifies the call.

Test paths the design names MUST appear in some impl report's `files_changed`:

- `tests/unit/test_auto_merge_classifier.py` — S01
- `tests/integration/test_auto_merge_phase1.py` — S02 (four NEW tests + one tightened skipped-event assertion)
- `tests/integration/test_auto_merge_partial_allowlist.py` — S03 (NEW)

`tests/unit/test_auto_merge_invoke.py` MUST NOT appear in any S0{1,2,3} `files_changed`. If it does, raise a CRITICAL scope finding — DB-touching tests for `attempt_resolution` belong in integration, not unit.

Missing required path → CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations in changed files vs `main` → each is a CRITICAL finding (`category: conventions`, exact code).

## Review Checklist

### 1. AC walk-through (NON-NEGOTIABLE — explicit per-AC verdict)

For each AC1–AC5 in `CR-00088_CR_Design.md`, record:

- AC reference + one-line restatement.
- Evidence (file:line OR test name + assertion text OR DB event snippet).
- Verdict: `PASS` / `FAIL` / `PARTIAL` (PARTIAL = AC partially observable, needs follow-up).
- If FAIL: severity (`CRITICAL`/`HIGH`) and the finding entry in the JSON below.

### 2. Cross-step partition invariants

Run each invariant check and record verdict + evidence:

- **Refuse-list precedence** — refuse-list step (1) returns BEFORE the new partition step (6). Evidence: read `orch/daemon/auto_merge.py:classify_conflicts` and confirm the refuse-list return is above the partition; AND read the new `test_refuselist_wins_over_partial_allowlist` test in `test_auto_merge_classifier.py`.
- **Order preservation** — both `eligible_files` and `deferred_files` reflect input ordering. Evidence: read the partition loop and confirm it is a single linear pass.
- **Phase-1 non-mutation** — `attempt_resolution` still aborts before any worktree write. Evidence: the `if config.phase >= PHASE_TESTS_ONLY: raise ValueError` guard (~line 855) is untouched; AND `tests/integration/test_auto_merge_partial_allowlist.py` asserts pre/post worktree hash equality.
- **Backward compat for `ClassificationResult`** — `deferred_files` has a trailing default; no existing constructor breaks. Evidence: `grep -rn "ClassificationResult(" orch/ tests/` and confirm every call site still compiles.
- **Backward compat for event metadata** — `conflict_files` and `eligible_files` keys are preserved in the metadata dicts; only additive keys (`allowlisted_files`, `deferred_files`) are introduced. Evidence: diff of `attempt_resolution` event-emission block + `merge_queue.py` skipped-event dict.
- **FAILED event carries `deferred_files`** — the `EVENT_AUTO_RESOLUTION_FAILED` branch in `attempt_resolution()` (~line 977) emits `deferred_files` in its metadata. Evidence: read the dict literal at that line; also confirm `test_attempt_resolution_failed_event_includes_deferred_files` asserts `event.event_metadata["deferred_files"]` with exact-value match. AC6 hinges on this.
- **`event_metadata` attribute used in tests, not `metadata`** — every new integration assertion uses `event.event_metadata[...]` (Python attribute). Any test that says `event.metadata[...]` is broken — raises `AttributeError` at runtime — HIGH finding.

### 3. Cross-step scope discipline

`git diff --name-only main..HEAD` matches the manifest's `scope.allowed_paths`. Any file outside (plus implicit `ai-dev/active/CR-00088/**` + `ai-dev/work/CR-00088/**`) is CRITICAL.

### 4. Test coverage cross-check

- The new RED-first unit tests + tightened existing tests cover every branch of the modified `classify_conflicts` step 6.
- The new integration test exercises the CR-00084 conflict shape end-to-end.
- No new test is silently quarantined / `xfail`'d / `skipif`'d.
- Run targeted tests:
  ```bash
  uv run pytest tests/unit/test_auto_merge_classifier.py tests/integration/test_auto_merge_phase1.py tests/integration/test_auto_merge_partial_allowlist.py -v
  ```
  All green. Record summary in the report.

### 5. Functional doc sanity

Re-read `CR-00088_Functional.md`. Does its plain-English description still match what shipped? If S01–S03 deviated from the design's behavioural promise, flag it HIGH and tell the operator what changed.

### 6. AC × test cross-walk table

In the report, provide an explicit table:

| AC | Test(s) covering it | File:line |
|----|---------------------|-----------|
| AC1 (partition correctness) | test_partial_allowlist_returns_partition | tests/unit/test_auto_merge_classifier.py:NN |
| AC2 (all-deferred skip) | test_all_deferred_keeps_skip_reason | tests/unit/test_auto_merge_classifier.py:NN |
| AC3 (refuse-list wins) | test_refuselist_wins_over_partial_allowlist | tests/unit/test_auto_merge_classifier.py:NN |
| AC4 (Phase-1 non-mutation) | tests/integration/test_auto_merge_partial_allowlist.py::test_cr00084_shape_partitions_event_metadata (worktree-hash assertion) | tests/integration/test_auto_merge_partial_allowlist.py:NN |
| AC5 (CR-00084 shape end-to-end) | tests/integration/test_auto_merge_partial_allowlist.py::test_cr00084_shape_partitions_event_metadata | tests/integration/test_auto_merge_partial_allowlist.py:NN |
| AC6 (FAILED event has deferred_files on LLM abstain/error) | test_attempt_resolution_failed_event_includes_deferred_files | tests/integration/test_auto_merge_phase1.py:NN |

Any AC with an empty row → CRITICAL.

### 7. Documentation sanity

- `docs/research/R-00076-llm-automated-merge-resolution.md` has the new partial-allowlist subsection AND it accurately describes what shipped.
- `ai-dev/active/AUTO_MERGE_RESOLUTION.md` has the one-line tracker entry with the correct date and CR number.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Missing AC, partition invariant broken, refuse-list precedence broken, scope violation, missing test, lint regression | Must fix before merge |
| **HIGH** | Significant bug, weak assertion, AC partially observable | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, convention drift | Should fix |
| **MEDIUM (suggestion)** | Design improvement | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "CR-00088",
  "implementation_steps": ["S01", "S02", "S03"],
  "verdict": "pass|fail",
  "ac_verdicts": [
    {"ac": "AC1", "verdict": "PASS|FAIL|PARTIAL", "evidence": "..."}
  ],
  "partition_invariants_verified": true,
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing|scope|docs",
      "file": "path/to/file.py",
      "line": 42,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "scope_violations": [],
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE findings AND every AC has a PASS verdict.
- `partition_invariants_verified`: explicit boolean for refuse-list precedence + order preservation + Phase-1 non-mutation + backward compat.
