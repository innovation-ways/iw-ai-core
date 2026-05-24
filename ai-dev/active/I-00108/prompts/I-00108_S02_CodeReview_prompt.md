# I00108_S02_CodeReview_prompt

**Work Item**: I-00108 -- `iw doc-update` new-doc without `--tier`/`--editorial-category` should be exit 2 usage error, not exit 3 TypeError
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Allowed exceptions: testcontainer fixtures in pytest, read-only `docker ps`/`docker logs`/`docker inspect`, `./ai-core.sh` / `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migration. You MUST NOT run alembic against the live orch DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00108 --json`.
- `ai-dev/active/I-00108/I-00108_Issue_Design.md` -- Design document.
- `ai-dev/active/I-00108/reports/I-00108_S01_Backend_report.md` -- S01 report.
- `orch/cli/doc_commands.py` -- the only production file S01 should have touched.
- `tests/integration/cli/test_doc_update_contract.py` -- read-only reference (S01 must NOT have edited it; that's S03).

## Output Files

- `ai-dev/active/I-00108/reports/I-00108_S02_CodeReview_report.md` -- Review report.

## Context

S01 added a runtime pre-check in `orch/cli/doc_commands.py::doc_update` so that a new-doc upsert missing `--tier`/`--editorial-category` exits 2 with a clean usage error instead of crashing with a `TypeError` surfaced as exit 3. Your job is to verify the change is minimal, correct, conventional, and does not break the update path.

## Read the Design Document FIRST

- `## Root Cause Analysis` — confirm the pre-check is in the CLI layer, not in `DocService`.
- `## Acceptance Criteria` — AC1 (exit 2 + clear stderr + no row created) and AC2 (xfail removed in S03, regression tests green) bound the contract.
- `## TDD Approach` — note that the reproduction test was authored by CR-00073 as `@pytest.mark.xfail(strict=True)`; S01 is expected to make it `XPASS(strict)`, S03 will remove the marker. S01 must NOT have touched any test file.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

If either reports NEW violations in `orch/cli/doc_commands.py`, file each as a **CRITICAL** finding with `"category": "conventions"`.

## Review Checklist

### 1. Pre-check placement

- The new branch lives **in `doc_update`'s CLI callback**, not inside `DocService`. Any change to `orch/doc_service.py` is a CRITICAL scope-creep finding — `create_doc`'s required-args contract is intentional.
- The new branch fires **only when** `existing is None` (no ProjectDoc yet) AND (`tier is None` OR `editorial_category is None`). If the condition fires on the update path (existing doc + missing tier) it would break `test_doc_update_existing_doc_update_without_tier_succeeds` in S03 — HIGH finding.
- The branch is positioned **before** any code path that can reach `DocService.create_doc()` (i.e. before `svc.upsert_doc(...)`). If a code path can still trip the `TypeError` (e.g. the pre-check runs AFTER `upsert_doc`, or only partially guards the condition), HIGH.

### 2. Exit code and message

- The refusal uses `output_error(ctx, msg, 2)` — matching the existing `output_error(ctx, ..., 1)` pattern in the same file. `click.UsageError(...)` or a raw `sys.exit(2)` is acceptable only if `output_error` is used elsewhere in `iw` with the same shape; flag any inconsistency.
- The message contains the substring `"tier"` (lowercase substring match; the contract test asserts `"tier" in (result.stderr or "").lower()`). A message that omits "tier" is a CRITICAL finding because the contract test will fail.
- The message names BOTH missing options (`--tier` and `--editorial-category`) so the operator knows what to add. A message that names only one is MEDIUM_FIXABLE.

### 3. `get_doc` call site reuse

- The original `doc_update` callback already calls `svc.get_doc(project_id, doc_id)` for the `old_content_hash` computation. The pre-check should **reuse the existing call**, not add a second one. If S01 introduced a duplicate `get_doc` call, that's a MEDIUM_FIXABLE finding (correctness is fine but two round-trips for one lookup is wasteful and the design doc explicitly asks for one).

### 4. Preserved behaviour

- The mutual-exclusivity check (`--content` + `--content-file` → exit 2) is untouched.
- The 10 MB content-size cap is untouched.
- The project-not-found path still returns exit 1.
- The `except Exception → exit 3 "Database error"` catch-all stays — this remains the correct behaviour for actual DB errors. Removing it is a CRITICAL finding.
- The JSON success-output shape is unchanged. The `doc-update` success-path tests in S03 will verify this.

### 5. No collateral changes

- Diff must be limited to `orch/cli/doc_commands.py`. Any change to `orch/doc_service.py`, `orch/cli/main.py`, or any other production file is a HIGH scope-creep finding.
- S01 must NOT have touched any test file. Editing `tests/integration/cli/test_doc_update_contract.py` (including removing the `@pytest.mark.xfail` marker) is a HIGH finding — that work belongs to S03.
- No new imports unless strictly necessary (the pre-check is a few lines using already-imported helpers).

### 6. Project conventions

- `snake_case`, single conditional, no new abstractions.
- The pre-check fits inside the existing `try` block (so the `except Exception` still catches genuine DB errors downstream) OR sits before the `try` block (so the `output_error(..., 2)` exits cleanly without passing through the catch-all). Either is acceptable; `output_error` does `sys.exit()` which `except Exception` does NOT catch (`SystemExit` is a `BaseException`), so position is a stylistic choice — flag any logic mistake.

### 7. TDD RED Evidence

S01's expected `tdd_red_evidence` is the `XPASS(strict)` line from the existing reproduction test:
`tests/integration/cli/test_doc_update_contract.py::test_doc_update_new_doc_without_tier_is_clean_usage_error XPASS(strict)`.
This is the RED→GREEN proof (the xfail flipped). Verify the report captures this verbatim or near-verbatim. An empty / "n/a" / generic value is a HIGH finding for this step.

## Test Verification (NON-NEGOTIABLE)

Run the targeted contract file:

```bash
uv run pytest tests/integration/cli/test_doc_update_contract.py -v --no-cov 2>&1 | tail -25
```

Expected: 5 passed + 1 `XPASS(strict)` (the xfail-flipped reproduction test). The `XPASS(strict)` is the GREEN signal — it is **not** a regression — because `strict=True` causes pytest to count an unexpected pass as a failure, the run will exit non-zero. That's expected at this step. Record the result; do NOT classify the strict-xfail-flip as a HIGH finding (S03 removes the marker).

Do NOT run `make test-unit`, `make test-integration`, or the full CLI contract suite — those are S10/S11 QV gates.

## Severity Levels

- **CRITICAL** — fix or merge will be blocked (test will fail, scope violated, security issue).
- **HIGH** — must fix before merge (wrong code path, missing assertion, broken contract).
- **MEDIUM_FIXABLE** — should fix this cycle (efficiency, message wording).
- **MEDIUM_SUGGESTION** — improvement idea, defer if tight.
- **LOW** — nit / style.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00108",
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
  "test_summary": "5 passed, 1 XPASS(strict) — the strict-xfail reproduction test now reports XPASS; S03 removes the marker",
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
