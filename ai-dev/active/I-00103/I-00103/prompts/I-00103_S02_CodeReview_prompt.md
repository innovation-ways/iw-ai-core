# I00103_S02_CodeReview_prompt

**Work Item**: I-00103 -- `merge_auto_resolution_failed` event drops per-file error string
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Allowed exceptions: testcontainer fixtures in pytest, read-only `docker ps`/`docker logs`/`docker inspect`, `./ai-core.sh` / `make`. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade head` / `alembic downgrade` / `alembic stamp` against the live orch DB. This item adds no migration. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00103 --json`.
- `ai-dev/active/I-00103/I-00103_Issue_Design.md` -- Design document.
- `ai-dev/active/I-00103/reports/I-00103_S01_Backend_report.md` -- S01 report.
- All files listed in S01's `files_changed` (expected: `orch/daemon/auto_merge.py`).

## Output Files

- `ai-dev/active/I-00103/reports/I-00103_S02_CodeReview_report.md` -- Review report.

## Context

S01 added `per_file_errors` to the `merge_auto_resolution_failed` event metadata payload. Your job is to verify the change is minimal, correct, conventional, and respects the schema in the design doc.

## Read the Design Document FIRST

Before opening code, read:

- `## Acceptance Criteria` — AC1 (field present + shape), AC2 (regression test), AC5 (500-char truncation). AC3 / AC4 are downstream (frontend) and not in scope for this review.
- `## TDD Approach` — note that the test files are owned by S05; do NOT expect S01 to have added them.
- `## Root Cause Analysis` — re-read the file:line landmarks to confirm S01's change is in the right place.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

If either reports NEW violations in `orch/daemon/auto_merge.py`, classify each as a **CRITICAL** finding with `"category": "conventions"`.

## Review Checklist

### 1. Schema correctness

- Does `per_file_errors` appear in the metadata dict of the `EVENT_AUTO_RESOLUTION_FAILED` `_emit_event(...)` call?
- Is each entry a dict with exactly the four keys `{file_path, error, cli_tool, model}`? Extra keys or missing keys are a HIGH finding.
- Is the list populated ONLY from `LLMCallResult` entries where `error is not None`? Verify that ABSTAIN entries and proposed-content entries are NOT leaking into the list.

### 2. Truncation cap

- Is each `error` value truncated to 500 chars (e.g. `call.error[:500]`)? A missing cap is a HIGH finding because the worst-case stderr at `auto_merge.py:784` is unbounded.
- Is the cap consistent — `[:500]` exactly, not 1000 / 256 / other? Consistency matters because the schema's worst-case-size analysis uses 500.

### 3. Order parity with `error_files`

- The design doc requires `per_file_errors[i].file_path` ordering to match `error_files[i]`. Verify both lists are built from the same iteration order over `llm_calls` (or one is derived from the other in a way that preserves order). If S01 iterates `llm_calls` separately for each list AND the source ordering is stable, that's fine; flag any ordering risk.

### 4. Payload-size cap

- The design doc's Requirement 4 asks for a one-line comment noting that the worst-case `per_file_errors` payload (≈ 3.5 KB) is comfortably under `config.max_event_metadata_bytes` (256 KB). Verify the comment is present or that an equivalent analysis is captured in the report.

### 5. No collateral changes

- S01 should NOT modify the `merge_auto_resolved` payload, the `merge_auto_resolution_attempted` payload, the `merge_auto_resolution_skipped` payload, the `LLMCallResult` dataclass, or the `invoke_llm_for_file` function. Any change outside the `EVENT_AUTO_RESOLUTION_FAILED` emission block at `auto_merge.py:961-981` is a HIGH finding (scope creep).
- Existing keys (`abstained_files`, `error_files`, `proposed_files`, `runtime_option_id`, `total_input_tokens`, `total_output_tokens`, `phase`) must be present and semantically identical to today.

### 6. Project conventions

- Match `snake_case` plural key naming.
- Match existing `_emit_event(...)` call style.
- No new imports needed for this change; flag any unexpected import additions.

### 7. Security

- No hardcoded secrets; the `error` strings come from `LLMCallResult` and may contain stderr text. Consider whether a 500-char stderr slice could contain credentials. The same risk exists today via `result.stderr[:500]` at `auto_merge.py:784` (not introduced by this fix), but if S01 has changed the truncation cap or removed it, flag it.

### 8. TDD RED Evidence

S01 is a Backend step BUT the test files are explicitly delegated to S05 by the design doc. The expected `tdd_red_evidence` value is `"n/a — reproduction + regression tests delegated to S05 tests-impl per design doc TDD Approach"` (or similar). Verify the report uses this form. Do NOT treat the absence of a RED run as a HIGH finding — the design says tests come in S05.

## Test Verification (NON-NEGOTIABLE)

Run the existing auto_merge Phase 1 integration tests to confirm no regression (this is the file that covers the `attempt_resolution` failed-event path — there is no `tests/unit/test_auto_merge.py`):

```bash
uv run pytest tests/integration/test_auto_merge_phase1.py -v 2>&1 | tail -30
```

Report results accurately.

## Severity Levels

(Standard table — CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.)

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00103",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
